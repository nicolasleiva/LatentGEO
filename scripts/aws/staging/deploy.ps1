[CmdletBinding()]
param(
    [string]$ConfigPath = "scripts/aws/staging/config.env",
    [switch]$SkipBudget,
    [switch]$SkipBuild,
    [switch]$EnableCredits,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Write-Step {
    param([string]$Message)
    Write-Host "[staging-deploy] $Message" -ForegroundColor Cyan
}

function Resolve-PathSafe {
    param(
        [string]$BasePath,
        [string]$PathValue
    )

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }

    return (Join-Path $BasePath $PathValue)
}

function Get-AwsCliPath {
    $awsCmd = Get-Command aws -ErrorAction SilentlyContinue
    if ($awsCmd) {
        return $awsCmd.Source
    }

    $fallback = 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
    if (Test-Path $fallback) {
        return $fallback
    }

    throw 'AWS CLI not found. Install AWS CLI v2 first.'
}

function Load-KeyValueFile {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        throw "File not found: $Path"
    }

    $map = @{}
    foreach ($rawLine in Get-Content $Path) {
        $line = $rawLine.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith('#')) {
            continue
        }

        $idx = $line.IndexOf('=')
        if ($idx -lt 1) {
            continue
        }

        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()

        if ($value.StartsWith('"') -and $value.EndsWith('"')) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        if ($value.StartsWith("'") -and $value.EndsWith("'")) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        $map[$key] = $value
    }

    return $map
}

function Get-ConfigValue {
    param(
        [hashtable]$Map,
        [string]$Key,
        [string]$DefaultValue = '',
        [switch]$Required
    )

    if ($Map.ContainsKey($Key) -and -not [string]::IsNullOrWhiteSpace($Map[$Key])) {
        return $Map[$Key]
    }

    if ($Required) {
        throw "Missing required config key: $Key"
    }

    return $DefaultValue
}

function To-Bool {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $false
    }

    switch ($Value.Trim().ToLowerInvariant()) {
        '1' { return $true }
        'true' { return $true }
        'yes' { return $true }
        'y' { return $true }
        default { return $false }
    }
}

function Invoke-Aws {
    param([string[]]$Arguments)

    $baseArgs = @()
    if (-not [string]::IsNullOrWhiteSpace($script:AwsProfile)) {
        $baseArgs += @('--profile', $script:AwsProfile)
    }

    if (-not [string]::IsNullOrWhiteSpace($script:AwsRegion)) {
        $baseArgs += @('--region', $script:AwsRegion)
    }

    $finalArgs = @($baseArgs + $Arguments)

    if ($DryRun) {
        Write-Host "DRYRUN aws $($finalArgs -join ' ')"
        return ''
    }

    $output = & $script:AwsCli @finalArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "AWS command failed: aws $($finalArgs -join ' ')`n$output"
    }

    return $output
}

function Get-StackOutput {
    param(
        [string]$StackName,
        [string]$OutputKey
    )

    if ($DryRun) {
        switch ($OutputKey) {
            'VpcId' { return 'vpc-dryrun' }
            'PublicSubnetIds' { return 'subnet-public-a,subnet-public-b' }
            'PrivateSubnetIds' { return 'subnet-private-a,subnet-private-b' }
            'ALBSecurityGroupId' { return 'sg-alb-dryrun' }
            'ECSSecurityGroupId' { return 'sg-ecs-dryrun' }
            'RDSSecurityGroupId' { return 'sg-rds-dryrun' }
            'RedisSecurityGroupId' { return 'sg-redis-dryrun' }
            'PublicSubnetAId' { return 'subnet-public-a' }
            'DBEndpointAddress' { return 'db.staging.local' }
            'RedisPrimaryEndpoint' { return 'redis.staging.local' }
            'CloudFrontDomainName' { return 'd111111abcdef8.cloudfront.net' }
            'AlbDnsName' { return 'alb-staging-123456.us-east-1.elb.amazonaws.com' }
            'ClusterName' { return 'auditor-geo-staging' }
            'BackendServiceName' { return 'auditor-geo-staging-backend-svc' }
            'FrontendServiceName' { return 'auditor-geo-staging-frontend-svc' }
            default { return "dryrun-$OutputKey" }
        }
    }

    $value = Invoke-Aws @(
        'cloudformation', 'describe-stacks',
        '--stack-name', $StackName,
        '--query', "Stacks[0].Outputs[?OutputKey=='$OutputKey'].OutputValue | [0]",
        '--output', 'text'
    )

    return ("$value").Trim()
}

function Deploy-Stack {
    param(
        [string]$StackName,
        [string]$TemplatePath,
        [hashtable]$Parameters,
        [string[]]$Capabilities = @()
    )

    $args = @(
        'cloudformation', 'deploy',
        '--stack-name', $StackName,
        '--template-file', $TemplatePath,
        '--no-fail-on-empty-changeset'
    )

    if ($Capabilities.Count -gt 0) {
        $args += '--capabilities'
        $args += $Capabilities
    }

    if ($Parameters.Count -gt 0) {
        $args += '--parameter-overrides'
        foreach ($entry in $Parameters.GetEnumerator()) {
            $args += "$($entry.Key)=$($entry.Value)"
        }
    }

    [void](Invoke-Aws $args)
}

function Ensure-EcrRepository {
    param([string]$RepositoryName)

    if ($DryRun) {
        Write-Step "DRYRUN ensure ECR repository: $RepositoryName"
        return
    }

    try {
        [void](Invoke-Aws @('ecr', 'describe-repositories', '--repository-names', $RepositoryName, '--output', 'json'))
        Write-Step "ECR repository exists: $RepositoryName"
    }
    catch {
        Write-Step "Creating ECR repository: $RepositoryName"
        [void](Invoke-Aws @(
            'ecr', 'create-repository',
            '--repository-name', $RepositoryName,
            '--image-scanning-configuration', 'scanOnPush=true',
            '--image-tag-mutability', 'MUTABLE'
        ))
    }
}

function Invoke-CheckedCommand {
    param(
        [string]$Exe,
        [string[]]$CmdArgs
    )

    if ($DryRun) {
        Write-Host "DRYRUN $Exe $($CmdArgs -join ' ')"
        return
    }

    & $Exe @CmdArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Exe $($CmdArgs -join ' ')"
    }
}

function Upsert-AppSecret {
    param(
        [string]$SecretName,
        [hashtable]$SecretPayload
    )

    $secretJson = ($SecretPayload | ConvertTo-Json -Compress)

    if ($DryRun) {
        Write-Step "DRYRUN upsert secret: $SecretName"
        return "arn:aws:secretsmanager:${script:AwsRegion}:000000000000:secret:${SecretName}"
    }

    $exists = $false
    try {
        [void](Invoke-Aws @('secretsmanager', 'describe-secret', '--secret-id', $SecretName, '--output', 'json'))
        $exists = $true
    }
    catch {
        $exists = $false
    }

    if ($exists) {
        Write-Step "Updating secret: $SecretName"
        [void](Invoke-Aws @('secretsmanager', 'update-secret', '--secret-id', $SecretName, '--secret-string', $secretJson))
    }
    else {
        Write-Step "Creating secret: $SecretName"
        [void](Invoke-Aws @('secretsmanager', 'create-secret', '--name', $SecretName, '--secret-string', $secretJson))
    }

    $arn = (Invoke-Aws @(
        'secretsmanager', 'describe-secret',
        '--secret-id', $SecretName,
        '--query', 'ARN',
        '--output', 'text'
    )).Trim()

    return $arn
}

function Get-FromMaps {
    param(
        [hashtable]$Primary,
        [hashtable]$Secondary,
        [string]$Key,
        [string]$DefaultValue = '',
        [switch]$Required
    )

    if ($Primary.ContainsKey($Key) -and -not [string]::IsNullOrWhiteSpace($Primary[$Key])) {
        return $Primary[$Key]
    }

    if ($Secondary.ContainsKey($Key) -and -not [string]::IsNullOrWhiteSpace($Secondary[$Key])) {
        return $Secondary[$Key]
    }

    if ($Required) {
        throw "Missing required value: $Key"
    }

    return $DefaultValue
}

function Ensure-Budget {
    param(
        [string]$AccountId,
        [string]$BudgetName,
        [string]$BudgetAmount,
        [string]$BudgetEmail
    )

    if ([string]::IsNullOrWhiteSpace($BudgetEmail)) {
        Write-Step 'Skipping budget creation because BUDGET_ALERT_EMAIL is empty.'
        return
    }

    try {
        [void](Invoke-Aws @('budgets', 'describe-budget', '--account-id', $AccountId, '--budget-name', $BudgetName))
        Write-Step "Budget already exists: $BudgetName"
        return
    }
    catch {
        Write-Step "Creating budget: $BudgetName"
    }

    $budgetObj = [ordered]@{
        BudgetName  = $BudgetName
        BudgetType  = 'COST'
        TimeUnit    = 'MONTHLY'
        BudgetLimit = [ordered]@{
            Amount = $BudgetAmount
            Unit   = 'USD'
        }
    }

    $notifObj = @(
        [ordered]@{
            Notification = [ordered]@{
                NotificationType   = 'ACTUAL'
                ComparisonOperator = 'GREATER_THAN'
                Threshold          = 80
                ThresholdType      = 'PERCENTAGE'
            }
            Subscribers  = @(
                [ordered]@{
                    SubscriptionType = 'EMAIL'
                    Address          = $BudgetEmail
                }
            )
        }
    )

    $budgetJson = ($budgetObj | ConvertTo-Json -Compress)
    $notifJson = ($notifObj | ConvertTo-Json -Compress)

    [void](Invoke-Aws @(
        'budgets', 'create-budget',
        '--account-id', $AccountId,
        '--budget', $budgetJson,
        '--notifications-with-subscribers', $notifJson
    ))
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$configFile = Resolve-PathSafe -BasePath $repoRoot -PathValue $ConfigPath
$config = Load-KeyValueFile -Path $configFile

$script:AwsCli = Get-AwsCliPath
$script:AwsProfile = Get-ConfigValue -Map $config -Key 'AWS_PROFILE' -DefaultValue ''
$script:AwsRegion = Get-ConfigValue -Map $config -Key 'AWS_REGION' -DefaultValue 'us-east-1'

$projectName = Get-ConfigValue -Map $config -Key 'PROJECT_NAME' -DefaultValue 'auditor-geo'
$environmentName = Get-ConfigValue -Map $config -Key 'ENVIRONMENT_NAME' -DefaultValue 'staging'
$accountId = Get-ConfigValue -Map $config -Key 'AWS_ACCOUNT_ID' -Required

$budgetAmount = Get-ConfigValue -Map $config -Key 'MONTHLY_BUDGET_USD' -DefaultValue '100'
$budgetEmail = Get-ConfigValue -Map $config -Key 'BUDGET_ALERT_EMAIL' -DefaultValue ''
$allowedIngressCidr = Get-ConfigValue -Map $config -Key 'ALLOWED_INGRESS_CIDR' -DefaultValue '0.0.0.0/0'

$dbName = Get-ConfigValue -Map $config -Key 'DB_NAME' -DefaultValue 'auditor_db'
$dbUser = Get-ConfigValue -Map $config -Key 'DB_USER' -DefaultValue 'auditor'
$dbPassword = Get-ConfigValue -Map $config -Key 'DB_PASSWORD' -Required
$dbInstanceClass = Get-ConfigValue -Map $config -Key 'DB_INSTANCE_CLASS' -DefaultValue 'db.t3.micro'
$dbAllocatedStorage = Get-ConfigValue -Map $config -Key 'DB_ALLOCATED_STORAGE' -DefaultValue '20'
$redisNodeType = Get-ConfigValue -Map $config -Key 'REDIS_NODE_TYPE' -DefaultValue 'cache.t3.micro'

$desiredBackendCount = Get-ConfigValue -Map $config -Key 'DESIRED_BACKEND_COUNT' -DefaultValue '1'
$desiredFrontendCount = Get-ConfigValue -Map $config -Key 'DESIRED_FRONTEND_COUNT' -DefaultValue '1'
$desiredWorkerCount = Get-ConfigValue -Map $config -Key 'DESIRED_WORKER_COUNT' -DefaultValue '0'

$sourceEnvFile = Resolve-PathSafe -BasePath $repoRoot -PathValue (Get-ConfigValue -Map $config -Key 'SOURCE_ENV_FILE' -DefaultValue '.env')
$secretName = Get-ConfigValue -Map $config -Key 'APP_SECRET_NAME' -DefaultValue "$projectName/$environmentName/app"

$configSkipBudget = To-Bool (Get-ConfigValue -Map $config -Key 'SKIP_BUDGET' -DefaultValue 'false')
$configSkipBuild = To-Bool (Get-ConfigValue -Map $config -Key 'SKIP_BUILD' -DefaultValue 'false')
$configEnableCredits = To-Bool (Get-ConfigValue -Map $config -Key 'ENABLE_CREDITS' -DefaultValue 'false')

if ($configSkipBudget) { $SkipBudget = $true }
if ($configSkipBuild) { $SkipBuild = $true }
if ($configEnableCredits) { $EnableCredits = $true }

Write-Step "Using AWS CLI: $script:AwsCli"
Write-Step "Project=$projectName Environment=$environmentName Region=$script:AwsRegion"

if (-not $DryRun) {
    $identity = Invoke-Aws @('sts', 'get-caller-identity', '--output', 'json') | Out-String | ConvertFrom-Json
    if ("$($identity.Account)" -ne "$accountId") {
        throw "Configured AWS_ACCOUNT_ID=$accountId but authenticated account is $($identity.Account)"
    }
    Write-Step "Authenticated as account: $($identity.Account)"
}

if (-not $SkipBudget) {
    $budgetName = "$projectName-$environmentName-monthly"
    Ensure-Budget -AccountId $accountId -BudgetName $budgetName -BudgetAmount $budgetAmount -BudgetEmail $budgetEmail
}
else {
    Write-Step 'Skipping budget phase.'
}

$networkStack = "$projectName-$environmentName-network"
$dataStack = "$projectName-$environmentName-data"
$appStack = "$projectName-$environmentName-app"

$networkTemplate = (Resolve-Path (Join-Path $PSScriptRoot 'templates/network.yml')).Path
$dataTemplate = (Resolve-Path (Join-Path $PSScriptRoot 'templates/data.yml')).Path
$appTemplate = (Resolve-Path (Join-Path $PSScriptRoot 'templates/app.yml')).Path

Write-Step "Deploying network stack: $networkStack"
Deploy-Stack -StackName $networkStack -TemplatePath $networkTemplate -Parameters @{
    ProjectName = $projectName
    EnvironmentName = $environmentName
    AllowedIngressCidr = $allowedIngressCidr
}

$vpcId = Get-StackOutput -StackName $networkStack -OutputKey 'VpcId'
$publicSubnetIds = Get-StackOutput -StackName $networkStack -OutputKey 'PublicSubnetIds'
$privateSubnetIds = Get-StackOutput -StackName $networkStack -OutputKey 'PrivateSubnetIds'
$albSg = Get-StackOutput -StackName $networkStack -OutputKey 'ALBSecurityGroupId'
$ecsSg = Get-StackOutput -StackName $networkStack -OutputKey 'ECSSecurityGroupId'
$rdsSg = Get-StackOutput -StackName $networkStack -OutputKey 'RDSSecurityGroupId'
$redisSg = Get-StackOutput -StackName $networkStack -OutputKey 'RedisSecurityGroupId'
$publicSubnetA = Get-StackOutput -StackName $networkStack -OutputKey 'PublicSubnetAId'

Write-Step "Deploying data stack: $dataStack"
Deploy-Stack -StackName $dataStack -TemplatePath $dataTemplate -Parameters @{
    ProjectName = $projectName
    EnvironmentName = $environmentName
    VpcId = $vpcId
    PrivateSubnetIds = $privateSubnetIds
    RDSSecurityGroupId = $rdsSg
    RedisSecurityGroupId = $redisSg
    DBName = $dbName
    DBUser = $dbUser
    DBPassword = $dbPassword
    DBInstanceClass = $dbInstanceClass
    DBAllocatedStorage = $dbAllocatedStorage
    RedisNodeType = $redisNodeType
}

$dbEndpoint = Get-StackOutput -StackName $dataStack -OutputKey 'DBEndpointAddress'
$redisEndpoint = Get-StackOutput -StackName $dataStack -OutputKey 'RedisPrimaryEndpoint'

if ([string]::IsNullOrWhiteSpace($dbEndpoint) -or [string]::IsNullOrWhiteSpace($redisEndpoint)) {
    throw 'Failed to resolve DB/Redis endpoints from data stack outputs.'
}

$dotenv = @{}
if (Test-Path $sourceEnvFile) {
    $dotenv = Load-KeyValueFile -Path $sourceEnvFile
}
else {
    Write-Step "Source env file not found, continuing without optional values: $sourceEnvFile"
}

$databaseUrl = "postgresql+psycopg2://${dbUser}:${dbPassword}@${dbEndpoint}:5432/${dbName}"
$redisUrl = "redis://${redisEndpoint}:6379/0"

$secretPayload = [ordered]@{
    DATABASE_URL = $databaseUrl
    REDIS_URL = $redisUrl
    CELERY_BROKER_URL = $redisUrl
    CELERY_RESULT_BACKEND = $redisUrl
    SECRET_KEY = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'SECRET_KEY' -Required
    ENCRYPTION_KEY = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'ENCRYPTION_KEY' -Required
    WEBHOOK_SECRET = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'WEBHOOK_SECRET' -Required
    BACKEND_INTERNAL_JWT_SECRET = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'BACKEND_INTERNAL_JWT_SECRET' -Required
    AUTH0_DOMAIN = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'AUTH0_DOMAIN' -Required
    AUTH0_CLIENT_ID = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'AUTH0_CLIENT_ID' -Required
    AUTH0_CLIENT_SECRET = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'AUTH0_CLIENT_SECRET' -Required
    AUTH0_SECRET = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'AUTH0_SECRET' -Required
    CORS_ORIGINS = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'CORS_ORIGINS' -DefaultValue 'https://staging.invalid'
    TRUSTED_HOSTS = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'TRUSTED_HOSTS' -DefaultValue 'staging.invalid'
    FRONTEND_URL = 'https://staging.invalid'
    APP_BASE_URL = 'https://staging.invalid'
    NEXT_PUBLIC_API_URL = 'https://staging.invalid'
    NEXT_PUBLIC_BACKEND_URL = 'https://staging.invalid'
    API_URL = 'https://staging.invalid'
    NVIDIA_API_KEY = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'NVIDIA_API_KEY' -DefaultValue ''
    NV_API_KEY = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'NV_API_KEY' -DefaultValue ''
    GOOGLE_PAGESPEED_API_KEY = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'GOOGLE_PAGESPEED_API_KEY' -DefaultValue ''
    CSE_ID = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'CSE_ID' -DefaultValue ''
    GITHUB_CLIENT_ID = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'GITHUB_CLIENT_ID' -DefaultValue ''
    GITHUB_CLIENT_SECRET = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'GITHUB_CLIENT_SECRET' -DefaultValue ''
    GITHUB_REDIRECT_URI = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'GITHUB_REDIRECT_URI' -DefaultValue ''
    GITHUB_WEBHOOK_SECRET = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'GITHUB_WEBHOOK_SECRET' -DefaultValue ''
    HUBSPOT_CLIENT_ID = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'HUBSPOT_CLIENT_ID' -DefaultValue ''
    HUBSPOT_CLIENT_SECRET = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'HUBSPOT_CLIENT_SECRET' -DefaultValue ''
    HUBSPOT_REDIRECT_URI = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'HUBSPOT_REDIRECT_URI' -DefaultValue ''
    DEFAULT_WEBHOOK_URL = Get-FromMaps -Primary $dotenv -Secondary $config -Key 'DEFAULT_WEBHOOK_URL' -DefaultValue ''
}

$appSecretArn = Upsert-AppSecret -SecretName $secretName -SecretPayload $secretPayload

$registry = "$accountId.dkr.ecr.$script:AwsRegion.amazonaws.com"
$backendRepo = "$projectName/backend"
$frontendRepo = "$projectName/frontend"

Ensure-EcrRepository -RepositoryName $backendRepo
Ensure-EcrRepository -RepositoryName $frontendRepo

$imageTag = Get-ConfigValue -Map $config -Key 'IMAGE_TAG' -DefaultValue ''
if ([string]::IsNullOrWhiteSpace($imageTag)) {
    if ($DryRun) {
        $imageTag = (Get-Date -Format 'yyyyMMddHHmm')
    }
    else {
        $imageTag = (git rev-parse --short HEAD).Trim()
    }
}

$backendImage = "${registry}/${backendRepo}:${imageTag}"
$frontendImage = "${registry}/${frontendRepo}:${imageTag}"
$backendLatest = "${registry}/${backendRepo}:staging-latest"
$frontendLatest = "${registry}/${frontendRepo}:staging-latest"

if (-not $SkipBuild) {
    Write-Step 'Logging in to ECR'
    $password = Invoke-Aws @('ecr', 'get-login-password')
    if (-not $DryRun) {
        $password | docker login --username AWS --password-stdin $registry | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw 'Docker login to ECR failed.'
        }
    }

    Write-Step "Building backend image: $backendImage"
    Invoke-CheckedCommand -Exe 'docker' -CmdArgs @('build', '-f', 'Dockerfile.backend', '-t', $backendImage, '.')
    Invoke-CheckedCommand -Exe 'docker' -CmdArgs @('tag', $backendImage, $backendLatest)

    Write-Step "Building frontend image: $frontendImage"
    Invoke-CheckedCommand -Exe 'docker' -CmdArgs @(
        'build',
        '-f', 'Dockerfile.frontend',
        '--build-arg', 'NEXT_PUBLIC_API_URL=https://staging.invalid',
        '--build-arg', 'NEXT_PUBLIC_BACKEND_URL=https://staging.invalid',
        '-t', $frontendImage,
        '.'
    )
    Invoke-CheckedCommand -Exe 'docker' -CmdArgs @('tag', $frontendImage, $frontendLatest)

    Write-Step 'Pushing backend images'
    Invoke-CheckedCommand -Exe 'docker' -CmdArgs @('push', $backendImage)
    Invoke-CheckedCommand -Exe 'docker' -CmdArgs @('push', $backendLatest)

    Write-Step 'Pushing frontend images'
    Invoke-CheckedCommand -Exe 'docker' -CmdArgs @('push', $frontendImage)
    Invoke-CheckedCommand -Exe 'docker' -CmdArgs @('push', $frontendLatest)
}
else {
    Write-Step 'Skipping image build/push phase.'
}

Write-Step "Deploying app stack: $appStack"
Deploy-Stack -StackName $appStack -TemplatePath $appTemplate -Parameters @{
    ProjectName = $projectName
    EnvironmentName = $environmentName
    VpcId = $vpcId
    PublicSubnetIds = $publicSubnetIds
    PrivateSubnetIds = $privateSubnetIds
    ALBSecurityGroupId = $albSg
    ECSSecurityGroupId = $ecsSg
    AppSecretArn = $appSecretArn
    BackendImageUri = $backendImage
    FrontendImageUri = $frontendImage
    WorkerImageUri = $backendImage
    DesiredBackendCount = $desiredBackendCount
    DesiredFrontendCount = $desiredFrontendCount
    DesiredWorkerCount = $desiredWorkerCount
} -Capabilities @('CAPABILITY_NAMED_IAM')

$cloudFrontDomain = Get-StackOutput -StackName $appStack -OutputKey 'CloudFrontDomainName'
$albDnsName = Get-StackOutput -StackName $appStack -OutputKey 'AlbDnsName'
$clusterName = Get-StackOutput -StackName $appStack -OutputKey 'ClusterName'
$backendServiceName = Get-StackOutput -StackName $appStack -OutputKey 'BackendServiceName'
$frontendServiceName = Get-StackOutput -StackName $appStack -OutputKey 'FrontendServiceName'

$publicBaseUrl = "https://$cloudFrontDomain"
$apiBaseUrl = "https://$cloudFrontDomain"
$trustedHost = "$cloudFrontDomain"

$secretPayload['APP_BASE_URL'] = $publicBaseUrl
$secretPayload['FRONTEND_URL'] = $publicBaseUrl
$secretPayload['NEXT_PUBLIC_API_URL'] = $apiBaseUrl
$secretPayload['NEXT_PUBLIC_BACKEND_URL'] = $apiBaseUrl
$secretPayload['API_URL'] = $apiBaseUrl
$secretPayload['CORS_ORIGINS'] = $publicBaseUrl
$secretPayload['TRUSTED_HOSTS'] = $trustedHost

[void](Upsert-AppSecret -SecretName $secretName -SecretPayload $secretPayload)

Write-Step 'Forcing ECS services to pick updated secret values'
[void](Invoke-Aws @('ecs', 'update-service', '--cluster', $clusterName, '--service', $backendServiceName, '--force-new-deployment'))
[void](Invoke-Aws @('ecs', 'update-service', '--cluster', $clusterName, '--service', $frontendServiceName, '--force-new-deployment'))

Write-Step 'Waiting for ECS services to become stable'
[void](Invoke-Aws @('ecs', 'wait', 'services-stable', '--cluster', $clusterName, '--services', $backendServiceName, $frontendServiceName))

if ($EnableCredits) {
    Write-Step 'Running optional credits activities script'
    $creditsScript = Join-Path $PSScriptRoot 'credits-activities.ps1'
    if (Test-Path $creditsScript) {
        & $creditsScript -ConfigPath $ConfigPath -PublicSubnetId $publicSubnetA -VpcId $vpcId
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'Credits activities script completed with warnings/errors. Release flow continues.'
        }
    }
    else {
        Write-Warning 'Credits activities script not found. Skipping.'
    }
}

Write-Step 'Deployment complete.'
Write-Host ''
Write-Host 'Outputs:' -ForegroundColor Green
Write-Host "- CloudFront URL: https://$cloudFrontDomain"
Write-Host "- ALB DNS: $albDnsName"
Write-Host "- ECS Cluster: $clusterName"
Write-Host "- Secret ARN: $appSecretArn"
Write-Host "- Backend image: $backendImage"
Write-Host "- Frontend image: $frontendImage"
