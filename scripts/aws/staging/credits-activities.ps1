[CmdletBinding()]
param(
    [string]$ConfigPath = 'scripts/aws/staging/config.env',
    [string]$PublicSubnetId,
    [string]$VpcId
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Step {
    param([string]$Message)
    Write-Host "[credits] $Message" -ForegroundColor Yellow
}

function Resolve-PathSafe {
    param([string]$BasePath, [string]$PathValue)
    if ([System.IO.Path]::IsPathRooted($PathValue)) { return $PathValue }
    return (Join-Path $BasePath $PathValue)
}

function Load-KeyValueFile {
    param([string]$Path)
    $map = @{}
    if (-not (Test-Path $Path)) { return $map }

    foreach ($rawLine in Get-Content $Path) {
        $line = $rawLine.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith('#')) { continue }
        $idx = $line.IndexOf('=')
        if ($idx -lt 1) { continue }
        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        $map[$key] = $value
    }

    return $map
}

function Get-AwsCliPath {
    $awsCmd = Get-Command aws -ErrorAction SilentlyContinue
    if ($awsCmd) { return $awsCmd.Source }
    $fallback = 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
    if (Test-Path $fallback) { return $fallback }
    throw 'AWS CLI not found.'
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
    $output = & $script:AwsCli @finalArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "AWS command failed: aws $($finalArgs -join ' ')`n$output"
    }

    return $output
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$configFile = Resolve-PathSafe -BasePath $repoRoot -PathValue $ConfigPath
$config = Load-KeyValueFile -Path $configFile

$script:AwsCli = Get-AwsCliPath
$script:AwsProfile = if ($config.ContainsKey('AWS_PROFILE')) { $config['AWS_PROFILE'] } else { '' }
$script:AwsRegion = if ($config.ContainsKey('AWS_REGION')) { $config['AWS_REGION'] } else { 'us-east-1' }

$project = if ($config.ContainsKey('PROJECT_NAME')) { $config['PROJECT_NAME'] } else { 'auditor-geo' }
$envName = if ($config.ContainsKey('ENVIRONMENT_NAME')) { $config['ENVIRONMENT_NAME'] } else { 'staging' }
$allowedCidr = if ($config.ContainsKey('ALLOWED_INGRESS_CIDR')) { $config['ALLOWED_INGRESS_CIDR'] } else { '0.0.0.0/0' }

try {
    Write-Step 'Validating AWS identity'
    [void](Invoke-Aws @('sts', 'get-caller-identity'))
}
catch {
    Write-Warning "Skipping credits script: AWS auth not ready. $_"
    exit 0
}

# 1) Launch EC2 instance (credit activity)
if (-not [string]::IsNullOrWhiteSpace($PublicSubnetId) -and -not [string]::IsNullOrWhiteSpace($VpcId)) {
    try {
        Write-Step 'Launching temporary EC2 instance for credit activity'

        $sgName = "$project-$envName-credits-ec2-sg"
        $sgId = ''
        try {
            $sgId = (Invoke-Aws @(
                'ec2', 'describe-security-groups',
                '--filters', "Name=group-name,Values=$sgName", "Name=vpc-id,Values=$VpcId",
                '--query', 'SecurityGroups[0].GroupId', '--output', 'text'
            )).Trim()
        }
        catch {
            $sgId = ''
        }

        if ([string]::IsNullOrWhiteSpace($sgId) -or $sgId -eq 'None') {
            $sgId = (Invoke-Aws @(
                'ec2', 'create-security-group',
                '--group-name', $sgName,
                '--description', 'Temporary SG for AWS credits EC2 activity',
                '--vpc-id', $VpcId,
                '--query', 'GroupId', '--output', 'text'
            )).Trim()

            [void](Invoke-Aws @(
                'ec2', 'authorize-security-group-ingress',
                '--group-id', $sgId,
                '--ip-permissions', "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$allowedCidr}]"
            ))
        }

        $amiId = (Invoke-Aws @(
            'ssm', 'get-parameter',
            '--name', '/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64',
            '--query', 'Parameter.Value',
            '--output', 'text'
        )).Trim()

        $instanceId = (Invoke-Aws @(
            'ec2', 'run-instances',
            '--image-id', $amiId,
            '--instance-type', 't3.micro',
            '--max-count', '1',
            '--min-count', '1',
            '--subnet-id', $PublicSubnetId,
            '--security-group-ids', $sgId,
            '--tag-specifications', "ResourceType=instance,Tags=[{Key=Name,Value=$project-$envName-credits-ec2},{Key=Purpose,Value=aws-credits}]",
            '--query', 'Instances[0].InstanceId',
            '--output', 'text'
        )).Trim()

        Write-Step "EC2 instance created: $instanceId"
        [void](Invoke-Aws @('ec2', 'wait', 'instance-running', '--instance-ids', $instanceId))
        [void](Invoke-Aws @('ec2', 'stop-instances', '--instance-ids', $instanceId))
        Write-Step 'EC2 instance stopped to control cost.'
    }
    catch {
        Write-Warning "EC2 credits activity failed: $_"
    }
}
else {
    Write-Warning 'Skipping EC2 credits activity (missing PublicSubnetId or VpcId).'
}

# 2) Create Lambda web app (credit activity)
try {
    Write-Step 'Creating/updating Lambda web app for credit activity'

    $lambdaRoleName = "$project-$envName-credits-lambda-role"
    $lambdaRoleArn = ''

    try {
        $lambdaRoleArn = (Invoke-Aws @('iam', 'get-role', '--role-name', $lambdaRoleName, '--query', 'Role.Arn', '--output', 'text')).Trim()
    }
    catch {
        $trustPolicy = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
        $lambdaRoleArn = (Invoke-Aws @(
            'iam', 'create-role',
            '--role-name', $lambdaRoleName,
            '--assume-role-policy-document', $trustPolicy,
            '--query', 'Role.Arn', '--output', 'text'
        )).Trim()
        [void](Invoke-Aws @('iam', 'attach-role-policy', '--role-name', $lambdaRoleName, '--policy-arn', 'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'))
        Start-Sleep -Seconds 10
    }

    $tempDir = Join-Path $env:TEMP "lambda-$project-$envName"
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
    $handlerPath = Join-Path $tempDir 'lambda_function.py'
    $zipPath = Join-Path $tempDir 'lambda.zip'

    @'
def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": "{\"message\":\"auditor-geo credits lambda ok\"}"
    }
'@ | Set-Content -Encoding UTF8 $handlerPath

    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Compress-Archive -Path $handlerPath -DestinationPath $zipPath -Force

    $functionName = "$project-$envName-credits-webapp"

    $functionExists = $true
    try {
        [void](Invoke-Aws @('lambda', 'get-function', '--function-name', $functionName))
    }
    catch {
        $functionExists = $false
    }

    if ($functionExists) {
        [void](Invoke-Aws @('lambda', 'update-function-code', '--function-name', $functionName, '--zip-file', "fileb://$zipPath"))
    }
    else {
        [void](Invoke-Aws @(
            'lambda', 'create-function',
            '--function-name', $functionName,
            '--runtime', 'python3.12',
            '--role', $lambdaRoleArn,
            '--handler', 'lambda_function.lambda_handler',
            '--timeout', '10',
            '--memory-size', '128',
            '--zip-file', "fileb://$zipPath"
        ))
    }

    try {
        [void](Invoke-Aws @('lambda', 'get-function-url-config', '--function-name', $functionName))
    }
    catch {
        [void](Invoke-Aws @('lambda', 'create-function-url-config', '--function-name', $functionName, '--auth-type', 'NONE'))
    }

    $functionUrl = (Invoke-Aws @('lambda', 'get-function-url-config', '--function-name', $functionName, '--query', 'FunctionUrl', '--output', 'text')).Trim()
    Write-Step "Lambda Function URL: $functionUrl"
}
catch {
    Write-Warning "Lambda credits activity failed: $_"
}

# 3) Bedrock playground invoke (credit activity)
try {
    Write-Step 'Running Bedrock test invocation (best effort)'
    $outputFile = Join-Path $env:TEMP "$project-$envName-bedrock-output.json"
    if (Test-Path $outputFile) { Remove-Item $outputFile -Force }

    [void](Invoke-Aws @(
        'bedrock-runtime', 'invoke-model',
        '--model-id', 'amazon.titan-text-lite-v1',
        '--content-type', 'application/json',
        '--accept', 'application/json',
        '--body', '{"inputText":"Say hello from auditor-geo staging setup"}',
        $outputFile
    ))

    Write-Step "Bedrock output saved to: $outputFile"
}
catch {
    Write-Warning "Bedrock credits activity failed (often model access/permissions): $_"
}

Write-Step 'Credits activities script finished (best effort).'
exit 0
