"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  startTransition,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  AlertCircle,
  ArrowLeft,
  Bot,
  CheckCircle2,
  Clipboard,
  FileText,
  Layers3,
  Loader2,
  MessageSquareText,
  Package,
  RefreshCw,
  SendHorizontal,
  ShoppingBag,
  UserRound,
} from "lucide-react";

import { Header } from "@/components/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { API_URL } from "@/lib/api-client";
import { fetchWithBackendAuth } from "@/lib/backend-auth";
import type { FixInputGroup } from "@/lib/types";

type OdooFixItem = {
  issue_code?: string;
  priority?: string;
  area?: string;
  page_path?: string;
  recommended_odoo_surface?: string;
  what_to_change?: string;
  why_it_matters?: string;
  evidence?: string;
  qa_check?: string;
};

type ArticleDeliverable = {
  title?: string;
  slug?: string;
  target_keyword?: string;
  focus_url?: string;
  citation_readiness_score?: number | null;
  schema_included?: boolean;
  source_count?: number | null;
  implementation_surface?: string;
  delivery_brief?: string;
  source?: string;
};

type EcommerceFix = {
  priority?: string;
  area?: string;
  recommended_odoo_surface?: string;
  what_to_change?: string;
  why_it_matters?: string;
  qa_check?: string;
};

type RootCauseItem = {
  title?: string;
  finding?: string;
  owner?: string;
};

type RootSnapshot = {
  path?: string;
  overall_score?: number | null;
  schema_score?: number | null;
  h1_score?: number | null;
};

type DeliverySummary = {
  fix_count?: number;
  article_count?: number;
  ecommerce_fix_count?: number;
  missing_required_inputs?: number;
  is_ecommerce?: boolean;
  articles_requested?: boolean;
  ecommerce_requested?: boolean;
  native_draft_count?: number;
  manual_review_count?: number;
};

type ImplementationPacket = {
  title?: string;
  branch_name_suggestion?: string;
  summary?: string;
  success_metrics?: string[];
  excluded_scope?: string[];
};

type CommerceContext = {
  has_analysis?: boolean;
  query?: string | null;
  market?: string | null;
  target_position?: number | null;
  top_result_domain?: string | null;
};

type ProductIntelligence = {
  is_ecommerce?: boolean;
  platform?: string | null;
  product_pages_count?: number | null;
  category_pages_count?: number | null;
};

type BriefingProfile = {
  add_articles?: boolean;
  article_count?: number | null;
  improve_ecommerce_fixes?: boolean;
  market?: string | null;
  language?: string | null;
  primary_goal?: string | null;
  team_owner?: string | null;
  rollout_notes?: string | null;
};

export type OdooConnectionItem = {
  id: string;
  label?: string | null;
  base_url: string;
  database: string;
  expected_email: string;
  odoo_version?: string | null;
  capabilities?: Record<string, any>;
  warnings?: string[];
  detected_user?: Record<string, any>;
  last_validated_at?: string | null;
  is_active?: boolean;
};

type OdooConnectionStatus = {
  selected?: boolean;
  status?: string;
  message?: string;
};

export type OdooSyncSummary = {
  status?: string;
  counts_by_model?: Record<string, number>;
  mapped_count?: number;
  unmapped_count?: number;
  mapped_audit_paths?: string[];
  unmapped_paths?: string[];
  last_synced_at?: string | null;
};

export type OdooDraftRow = {
  id: string;
  action_key: string;
  draft_type: string;
  status: string;
  title?: string | null;
  target_model?: string | null;
  target_record_id?: string | null;
  target_path?: string | null;
  external_record_id?: string | null;
  draft_payload?: Record<string, any>;
  evidence?: Record<string, any>;
  acceptance_criteria?: string | null;
  error_message?: string | null;
  updated_at?: string | null;
};

export type OdooDraftSummary = {
  native_draft_count?: number;
  draft_count?: number;
  manual_review_count?: number;
  failed_count?: number;
  last_prepared_at?: string | null;
};

export type OdooDraftsPayload = {
  native_created: OdooDraftRow[];
  draft: OdooDraftRow[];
  manual_review: OdooDraftRow[];
  failed: OdooDraftRow[];
  summary?: OdooDraftSummary;
};

export type PlanPayload = {
  selected_connection?: OdooConnectionItem | null;
  connection_status?: OdooConnectionStatus;
  capabilities?: Record<string, any>;
  sync_summary?: OdooSyncSummary;
  native_draft_count?: number;
  manual_review_count?: number;
  blocked_scope?: string[];
  implementation_packet?: ImplementationPacket;
  delivery_summary?: DeliverySummary;
  briefing_profile?: BriefingProfile;
  root_page_snapshot?: RootSnapshot;
  report_excerpt?: string | null;
  odoo_ready_fixes?: OdooFixItem[];
  article_deliverables?: ArticleDeliverable[];
  ecommerce_fixes?: EcommerceFix[];
  commerce_context?: CommerceContext;
  commerce_root_causes?: RootCauseItem[];
  product_intelligence?: ProductIntelligence;
  required_inputs?: FixInputGroup[];
  qa_checklist?: string[];
  notes?: string[];
  generated_at?: string;
};

type ConnectionDraft = {
  base_url: string;
  database: string;
  email: string;
  api_key: string;
};

type BriefDraft = {
  primary_goal: string;
  market: string;
  language: string;
  add_articles: boolean;
  article_count: string;
  improve_ecommerce_fixes: boolean;
  team_owner: string;
  rollout_notes: string;
};

type BriefStepOption = {
  label: string;
  value: string;
  description: string;
};

type BriefStep = {
  id:
    | "primary_goal"
    | "market"
    | "language"
    | "add_articles"
    | "article_count"
    | "improve_ecommerce_fixes"
    | "team_owner"
    | "rollout_notes";
  type: "choice" | "text" | "textarea";
  label: string;
  assistantMessage: string;
  required?: boolean;
  placeholder?: string;
  options?: BriefStepOption[];
};

type FixChatStep = {
  id: string;
  groupId: string;
  issueCode: string;
  pagePath: string;
  required: boolean;
  prompt?: string;
  field: FixInputGroup["fields"][number];
  loading?: boolean;
  assistantMessage?: string;
  suggestedValue?: string;
  confidence?: string;
};

type FixInputChatResponse = {
  assistant_message: string;
  suggested_value: string;
  confidence: string;
};

type FixInputsResponse = {
  audit_id: number;
  missing_inputs: FixInputGroup[];
  missing_required: number;
};

const LANGUAGE_OPTIONS: BriefStepOption[] = [
  {
    label: "English",
    value: "en",
    description: "Global or executive rollout.",
  },
  { label: "Spanish", value: "es", description: "LATAM or Spain rollout." },
  {
    label: "Portuguese",
    value: "pt-br",
    description: "Brazil-focused rollout.",
  },
  { label: "French", value: "fr", description: "French-speaking rollout." },
];

const GOAL_OPTIONS = (isEcommerce: boolean): BriefStepOption[] => [
  {
    label: "Template SEO Rollout",
    value:
      "Strengthen template-level SEO, entity clarity, and editorial trust signals in Odoo.",
    description: "Best for template and structured-data consistency.",
  },
  {
    label: "Content Authority",
    value:
      "Expand content authority with Odoo pages and blog modules aligned to audited opportunities.",
    description: "Best when content expansion is part of the rollout.",
  },
  ...(isEcommerce
    ? [
        {
          label: "Commercial Growth",
          value:
            "Improve commercial page visibility across homepage, category, and product templates.",
          description:
            "Best for category, PDP, and homepage visibility growth.",
        },
      ]
    : []),
];

function formatLanguage(value: string) {
  return (
    LANGUAGE_OPTIONS.find((item) => item.value === value)?.label ||
    value ||
    "Not set"
  );
}

function deriveBriefDraft(
  audit: any,
  plan: PlanPayload | null | undefined,
): BriefDraft {
  const briefing = plan?.briefing_profile || {};
  const articleCount =
    briefing.article_count ?? plan?.delivery_summary?.article_count;
  return {
    primary_goal: String(briefing.primary_goal || ""),
    market: String(briefing.market || audit?.market || ""),
    language: String(briefing.language || audit?.language || "en"),
    add_articles: Boolean(briefing.add_articles),
    article_count: articleCount ? String(articleCount) : "3",
    improve_ecommerce_fixes:
      briefing.improve_ecommerce_fixes ??
      Boolean(plan?.delivery_summary?.is_ecommerce),
    team_owner: String(briefing.team_owner || ""),
    rollout_notes: String(briefing.rollout_notes || ""),
  };
}

function deriveConnectionDraft(
  audit: any,
  plan: PlanPayload | null | undefined,
): ConnectionDraft {
  const selected = plan?.selected_connection;
  return {
    base_url: String(selected?.base_url || audit?.url || ""),
    database: String(selected?.database || ""),
    email: String(selected?.expected_email || audit?.user_email || ""),
    api_key: "",
  };
}

function emptyDraftsPayload(): OdooDraftsPayload {
  return {
    native_created: [],
    draft: [],
    manual_review: [],
    failed: [],
    summary: {
      native_draft_count: 0,
      draft_count: 0,
      manual_review_count: 0,
      failed_count: 0,
      last_prepared_at: null,
    },
  };
}

function buildBriefSteps(
  draft: BriefDraft,
  isEcommerce: boolean,
  marketHint: string,
  supportsArticles: boolean,
) {
  const steps: BriefStep[] = [
    {
      id: "primary_goal",
      type: "choice",
      label: "Primary goal",
      required: true,
      assistantMessage:
        "First define the delivery objective. This shapes how the Odoo pack is framed for the client team.",
      options: GOAL_OPTIONS(isEcommerce),
    },
    {
      id: "market",
      type: "text",
      label: "Priority market",
      required: true,
      placeholder: marketHint || "LATAM, US, EMEA, or specific country",
      assistantMessage:
        "Which market should this rollout prioritize? I use this to align language, examples, and commercial emphasis.",
    },
    {
      id: "language",
      type: "choice",
      label: "Delivery language",
      required: true,
      assistantMessage:
        "Choose the working language for templates and content.",
      options: LANGUAGE_OPTIONS,
    },
  ];

  if (supportsArticles) {
    steps.push({
      id: "add_articles",
      type: "choice",
      label: "Include article deliverables",
      required: true,
      assistantMessage:
        "Should the pack include editorial pieces for Odoo blog and support pages?",
      options: [
        {
          label: "Yes, include them",
          value: "yes",
          description:
            "Adds article deliverables grounded in audited opportunities.",
        },
        {
          label: "No, keep technical",
          value: "no",
          description:
            "Keeps the pack focused on implementation fixes and templates.",
        },
      ],
    });
  }

  if (supportsArticles && draft.add_articles) {
    steps.push({
      id: "article_count",
      type: "choice",
      label: "Article count",
      required: true,
      assistantMessage:
        "How many article deliverables should this rollout include?",
      options: [
        { label: "3 articles", value: "3", description: "Lean rollout." },
        { label: "5 articles", value: "5", description: "Balanced rollout." },
        {
          label: "8 articles",
          value: "8",
          description: "Broader editorial push.",
        },
      ],
    });
  }

  if (isEcommerce) {
    steps.push({
      id: "improve_ecommerce_fixes",
      type: "choice",
      label: "Include ecommerce fixes",
      required: true,
      assistantMessage:
        "This audit looks ecommerce-relevant. Should the pack include category, PDP, and merchandising improvements?",
      options: [
        {
          label: "Yes, include ecommerce",
          value: "yes",
          description: "Adds product, category, and commercial page actions.",
        },
        {
          label: "No, exclude ecommerce",
          value: "no",
          description: "Keeps the pack focused on non-commerce templates.",
        },
      ],
    });
  }

  steps.push(
    {
      id: "team_owner",
      type: "text",
      label: "Delivery owner",
      required: false,
      placeholder: isEcommerce
        ? "Regional ecommerce team"
        : "SEO / web content team",
      assistantMessage: "Who will own implementation on the client side?",
    },
    {
      id: "rollout_notes",
      type: "textarea",
      label: "Rollout notes",
      required: false,
      placeholder:
        "Example: avoid checkout templates, keep legal pages untouched, prioritize homepage and top categories first.",
      assistantMessage:
        "Add any rollout constraints that the Odoo team should respect.",
    },
  );

  return steps;
}

function buildFixChatSteps(groups: FixInputGroup[]): FixChatStep[] {
  const orderedGroups = [
    ...groups.filter((group) => group.required),
    ...groups.filter((group) => !group.required),
  ];
  return orderedGroups.flatMap((group) =>
    group.fields.map((field) => ({
      id: `${group.id}:${field.key}`,
      groupId: group.id,
      issueCode: group.issue_code,
      pagePath: group.page_path,
      required: Boolean(field.required || group.required),
      prompt: group.prompt,
      field,
    })),
  );
}

function buildInputValues(groups: FixInputGroup[]) {
  const values: Record<string, Record<string, string>> = {};
  groups.forEach((group) => {
    values[group.id] = {};
    group.fields.forEach((field) => {
      values[group.id][field.key] = field.value ?? "";
    });
  });
  return values;
}

function parseJson<T>(raw: string): T {
  return raw ? (JSON.parse(raw) as T) : ({} as T);
}

function extractErrorMessage(payload: any, fallback: string) {
  if (!payload) return fallback;
  if (typeof payload.detail === "string" && payload.detail.trim()) {
    return payload.detail;
  }
  if (
    payload.detail &&
    typeof payload.detail === "object" &&
    typeof payload.detail.message === "string"
  ) {
    return payload.detail.message;
  }
  if (typeof payload.message === "string" && payload.message.trim()) {
    return payload.message;
  }
  return fallback;
}

export default function OdooDeliveryPageClient({
  auditId,
  locale,
  initialAudit,
  initialPlan,
  initialConnections,
  initialSyncSummary,
  initialDrafts,
  initialError,
}: {
  auditId: string;
  locale: string;
  initialAudit?: any | null;
  initialPlan?: PlanPayload | null;
  initialConnections?: OdooConnectionItem[];
  initialSyncSummary?: OdooSyncSummary | null;
  initialDrafts?: OdooDraftsPayload | null;
  initialError?: string | null;
}) {
  const [audit, setAudit] = useState<any>(initialAudit ?? null);
  const [plan, setPlan] = useState<PlanPayload | null>(initialPlan ?? null);
  const [connections, setConnections] = useState<OdooConnectionItem[]>(
    initialConnections ?? [],
  );
  const [syncSummary, setSyncSummary] = useState<OdooSyncSummary>(
    initialSyncSummary ?? initialPlan?.sync_summary ?? {},
  );
  const [drafts, setDrafts] = useState<OdooDraftsPayload>(
    initialDrafts ?? emptyDraftsPayload(),
  );
  const [error, setError] = useState<string | null>(initialError ?? null);
  const [copied, setCopied] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [connectionDraft, setConnectionDraft] = useState<ConnectionDraft>(() =>
    deriveConnectionDraft(initialAudit, initialPlan),
  );
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [connectionSuccess, setConnectionSuccess] = useState<string | null>(
    null,
  );
  const [connectionTesting, setConnectionTesting] = useState(false);
  const [connectionSaving, setConnectionSaving] = useState(false);
  const [assigningConnectionId, setAssigningConnectionId] = useState<
    string | null
  >(null);
  const [syncing, setSyncing] = useState(false);
  const [preparingDrafts, setPreparingDrafts] = useState(false);

  const [briefDraft, setBriefDraft] = useState<BriefDraft>(() =>
    deriveBriefDraft(initialAudit, initialPlan),
  );
  const [briefStepIndex, setBriefStepIndex] = useState(0);
  const [briefInputValue, setBriefInputValue] = useState("");
  const [briefError, setBriefError] = useState<string | null>(null);
  const [briefSuccess, setBriefSuccess] = useState<string | null>(null);
  const [briefSaving, setBriefSaving] = useState(false);

  const [missingInputs, setMissingInputs] = useState<FixInputGroup[]>(
    initialPlan?.required_inputs || [],
  );
  const [inputValues, setInputValues] = useState<
    Record<string, Record<string, string>>
  >(() => buildInputValues(initialPlan?.required_inputs || []));
  const [chatSteps, setChatSteps] = useState<FixChatStep[]>(
    buildFixChatSteps(initialPlan?.required_inputs || []),
  );
  const [currentFixStepIndex, setCurrentFixStepIndex] = useState(0);
  const [stepError, setStepError] = useState<string | null>(null);
  const [fixSuccess, setFixSuccess] = useState<string | null>(null);
  const [inputsSaving, setInputsSaving] = useState(false);

  const router = useRouter();
  const backendUrl = API_URL;
  const auditDetailHref = useMemo(
    () => `/${locale}/audits/${auditId}`,
    [auditId, locale],
  );
  const isEcommerce = Boolean(plan?.delivery_summary?.is_ecommerce);
  const selectedConnection = plan?.selected_connection || null;
  const hasSelectedConnection = Boolean(selectedConnection?.id);
  const capabilities =
    plan?.capabilities || selectedConnection?.capabilities || {};
  const supportsArticles = Boolean(capabilities.website_blog);
  const supportsEcommerce = Boolean(
    capabilities.website_sale || plan?.delivery_summary?.is_ecommerce,
  );
  const briefSteps = useMemo(
    () =>
      buildBriefSteps(
        briefDraft,
        supportsEcommerce,
        plan?.briefing_profile?.market || audit?.market || "",
        supportsArticles,
      ),
    [
      audit?.market,
      briefDraft,
      supportsArticles,
      supportsEcommerce,
      plan?.briefing_profile?.market,
    ],
  );
  const activeBriefStep = briefSteps[briefStepIndex] || null;
  const activeFixStep = chatSteps[currentFixStepIndex] || null;
  const briefingIntro = supportsEcommerce
    ? "I’ll shape this as a client-ready Odoo rollout brief for templates, editorial scope, and ecommerce surfaces."
    : "I’ll shape this as a client-ready Odoo rollout brief for templates, editorial scope, and implementation constraints.";

  const applyServerState = useCallback(
    (nextAudit: any, nextPlan: PlanPayload) => {
      startTransition(() => {
        setAudit(nextAudit);
        setPlan(nextPlan);
        setMissingInputs(nextPlan?.required_inputs || []);
        setSyncSummary(nextPlan?.sync_summary || {});
        setConnectionDraft(deriveConnectionDraft(nextAudit, nextPlan));
        setError(null);
      });
    },
    [],
  );

  const loadPlan = useCallback(async () => {
    setRefreshing(true);
    try {
      const [auditResponse, planResponse, connectionsResponse] =
        await Promise.all([
          fetchWithBackendAuth(`${backendUrl}/api/v1/audits/${auditId}`),
          fetchWithBackendAuth(
            `${backendUrl}/api/v1/odoo/delivery-plan/${auditId}`,
          ),
          fetchWithBackendAuth(`${backendUrl}/api/v1/odoo/connections`),
        ]);
      const [auditRaw, planRaw, connectionsRaw] = await Promise.all([
        auditResponse.text(),
        planResponse.text(),
        connectionsResponse.text(),
      ]);
      if (!planResponse.ok) {
        throw new Error(
          (planRaw ? parseJson<any>(planRaw)?.detail : null) ||
            `Unable to refresh Odoo delivery pack (${planResponse.status})`,
        );
      }
      const nextPlan = parseJson<PlanPayload>(planRaw);
      const nextAudit = auditResponse.ok ? parseJson<any>(auditRaw) : audit;
      applyServerState(nextAudit, nextPlan);
      if (connectionsResponse.ok) {
        setConnections(parseJson<OdooConnectionItem[]>(connectionsRaw) || []);
      }
      if (nextPlan.selected_connection?.id) {
        const [syncResponse, draftsResponse] = await Promise.all([
          fetchWithBackendAuth(`${backendUrl}/api/v1/odoo/sync/${auditId}`),
          fetchWithBackendAuth(`${backendUrl}/api/v1/odoo/drafts/${auditId}`),
        ]);
        const [syncRaw, draftsRaw] = await Promise.all([
          syncResponse.text(),
          draftsResponse.text(),
        ]);
        if (syncResponse.ok) {
          setSyncSummary(
            (parseJson<any>(syncRaw)?.summary as OdooSyncSummary) || {},
          );
        }
        if (draftsResponse.ok) {
          setDrafts(
            parseJson<OdooDraftsPayload>(draftsRaw) || emptyDraftsPayload(),
          );
        } else {
          setDrafts(emptyDraftsPayload());
        }
      } else {
        setSyncSummary(nextPlan.sync_summary || {});
        setDrafts(emptyDraftsPayload());
      }
    } catch (nextError: any) {
      setError(nextError?.message || "Unable to refresh Odoo delivery pack.");
    } finally {
      setRefreshing(false);
    }
  }, [applyServerState, audit, auditId, backendUrl]);

  useEffect(() => {
    if (!plan && !error) {
      void loadPlan();
    }
  }, [error, loadPlan, plan]);

  useEffect(() => {
    setBriefDraft(deriveBriefDraft(audit, plan));
  }, [audit, plan]);

  useEffect(() => {
    setConnectionDraft(deriveConnectionDraft(audit, plan));
  }, [audit, plan]);

  useEffect(() => {
    if (briefStepIndex > briefSteps.length) {
      setBriefStepIndex(briefSteps.length);
    }
  }, [briefStepIndex, briefSteps.length]);

  useEffect(() => {
    if (currentFixStepIndex > chatSteps.length) {
      setCurrentFixStepIndex(chatSteps.length);
    }
  }, [chatSteps.length, currentFixStepIndex]);

  useEffect(() => {
    if (!activeBriefStep) {
      setBriefInputValue("");
      return;
    }
    const valueMap: Record<BriefStep["id"], string> = {
      primary_goal: briefDraft.primary_goal,
      market: briefDraft.market,
      language: briefDraft.language,
      add_articles: briefDraft.add_articles ? "yes" : "no",
      article_count: briefDraft.article_count,
      improve_ecommerce_fixes: briefDraft.improve_ecommerce_fixes
        ? "yes"
        : "no",
      team_owner: briefDraft.team_owner,
      rollout_notes: briefDraft.rollout_notes,
    };
    setBriefInputValue(valueMap[activeBriefStep.id] || "");
  }, [activeBriefStep, briefDraft]);

  useEffect(() => {
    const nextMissing = plan?.required_inputs || [];
    setMissingInputs(nextMissing);
  }, [plan?.generated_at, plan?.required_inputs]);

  useEffect(() => {
    setInputValues(buildInputValues(missingInputs));
    setChatSteps(buildFixChatSteps(missingInputs));
    setCurrentFixStepIndex(0);
    setStepError(null);
    setFixSuccess(null);
  }, [missingInputs]);

  const copyPacket = async () => {
    if (!plan?.implementation_packet) return;
    const lines = [
      plan.implementation_packet.title || "Odoo Delivery Pack",
      plan.implementation_packet.summary || "",
      "",
      "Briefing profile:",
      `- Goal: ${briefDraft.primary_goal || "n/a"}`,
      `- Market: ${briefDraft.market || "n/a"}`,
      `- Language: ${formatLanguage(briefDraft.language)}`,
      `- Articles: ${briefDraft.add_articles ? "yes" : "no"}`,
      `- Ecommerce fixes: ${briefDraft.improve_ecommerce_fixes ? "yes" : "no"}`,
      "",
      "Odoo delivery fixes:",
      ...(plan.odoo_ready_fixes || []).map(
        (item) =>
          `- [${item.priority || "MEDIUM"}] ${item.page_path || "/"} - ${item.what_to_change || item.why_it_matters || ""}`,
      ),
    ].join("\n");
    await navigator.clipboard.writeText(lines);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  const updateBriefDraft = (stepId: BriefStep["id"], value: string) => {
    setBriefDraft((prev) => {
      switch (stepId) {
        case "primary_goal":
          return { ...prev, primary_goal: value };
        case "market":
          return { ...prev, market: value };
        case "language":
          return { ...prev, language: value };
        case "add_articles":
          return { ...prev, add_articles: value === "yes" };
        case "article_count":
          return { ...prev, article_count: value || "3" };
        case "improve_ecommerce_fixes":
          return { ...prev, improve_ecommerce_fixes: value === "yes" };
        case "team_owner":
          return { ...prev, team_owner: value };
        case "rollout_notes":
          return { ...prev, rollout_notes: value };
        default:
          return prev;
      }
    });
  };

  const restartBriefing = () => {
    setBriefDraft(deriveBriefDraft(audit, plan));
    setBriefStepIndex(0);
    setBriefError(null);
    setBriefSuccess(null);
  };

  const advanceBriefStep = () => {
    setBriefStepIndex((prev) =>
      prev >= briefSteps.length - 1 ? briefSteps.length : prev + 1,
    );
  };

  const handleBriefChoice = (option: BriefStepOption) => {
    if (!activeBriefStep) return;
    updateBriefDraft(activeBriefStep.id, option.value);
    setBriefError(null);
    setBriefSuccess(null);
    advanceBriefStep();
  };

  const submitBriefTextStep = (skipOptional = false) => {
    if (!activeBriefStep) return;
    const nextValue = (skipOptional ? "" : briefInputValue).trim();
    if (activeBriefStep.required && !nextValue) {
      setBriefError(`Please provide ${activeBriefStep.label.toLowerCase()}.`);
      return;
    }
    updateBriefDraft(activeBriefStep.id, nextValue);
    setBriefError(null);
    setBriefSuccess(null);
    advanceBriefStep();
  };

  const saveBriefing = async () => {
    setBriefSaving(true);
    setBriefError(null);
    setBriefSuccess(null);
    try {
      const response = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/odoo/delivery-brief/${auditId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            add_articles: supportsArticles ? briefDraft.add_articles : false,
            article_count:
              supportsArticles && briefDraft.add_articles
                ? Number(briefDraft.article_count || 3)
                : null,
            improve_ecommerce_fixes: supportsEcommerce
              ? briefDraft.improve_ecommerce_fixes
              : false,
            market: briefDraft.market,
            language: briefDraft.language,
            primary_goal: briefDraft.primary_goal,
            team_owner: briefDraft.team_owner,
            rollout_notes: briefDraft.rollout_notes,
          }),
        },
      );
      const raw = await response.text();
      const payload = raw ? parseJson<any>(raw) : {};
      if (!response.ok) {
        throw new Error(
          payload?.detail ||
            `Unable to save Odoo delivery brief (${response.status})`,
        );
      }
      applyServerState(
        {
          ...(audit || {}),
          market: payload.market,
          language: payload.language,
          intake_profile: payload.intake_profile,
        },
        payload.plan,
      );
      setBriefSuccess("Odoo delivery brief saved and pack refreshed.");
      startTransition(() => {
        router.refresh();
      });
    } catch (nextError: any) {
      setBriefError(
        nextError?.message || "Unable to save Odoo delivery brief.",
      );
    } finally {
      setBriefSaving(false);
    }
  };

  const updateConnectionField = (
    field: keyof ConnectionDraft,
    value: string,
  ) => {
    setConnectionDraft((prev) => ({ ...prev, [field]: value }));
  };

  const testConnection = async () => {
    setConnectionTesting(true);
    setConnectionError(null);
    setConnectionSuccess(null);
    try {
      const response = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/odoo/connections/test`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(connectionDraft),
        },
      );
      const raw = await response.text();
      const payload = raw ? parseJson<any>(raw) : {};
      if (!response.ok) {
        throw new Error(
          extractErrorMessage(
            payload,
            `Unable to test Odoo connection (${response.status})`,
          ),
        );
      }
      setConnectionSuccess(
        `Connection verified${payload.version ? ` · Odoo ${payload.version}` : ""}.`,
      );
    } catch (nextError: any) {
      setConnectionError(
        nextError?.message || "Unable to validate the Odoo connection.",
      );
    } finally {
      setConnectionTesting(false);
    }
  };

  const assignConnection = async (connectionId: string) => {
    setAssigningConnectionId(connectionId);
    setConnectionError(null);
    setConnectionSuccess(null);
    try {
      const response = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/odoo/audits/${auditId}/connection`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ connection_id: connectionId }),
        },
      );
      const raw = await response.text();
      const payload = raw ? parseJson<any>(raw) : {};
      if (!response.ok) {
        throw new Error(
          extractErrorMessage(
            payload,
            `Unable to assign Odoo connection (${response.status})`,
          ),
        );
      }
      applyServerState(audit, payload.plan);
      setConnectionSuccess("Odoo connection linked to this audit.");
      await loadPlan();
      startTransition(() => {
        router.refresh();
      });
    } catch (nextError: any) {
      setConnectionError(
        nextError?.message ||
          "Unable to link the Odoo connection to this audit.",
      );
    } finally {
      setAssigningConnectionId(null);
    }
  };

  const saveAndConnect = async () => {
    setConnectionSaving(true);
    setConnectionError(null);
    setConnectionSuccess(null);
    try {
      const response = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/odoo/connections`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(connectionDraft),
        },
      );
      const raw = await response.text();
      const payload = raw ? parseJson<OdooConnectionItem | any>(raw) : {};
      if (!response.ok) {
        throw new Error(
          extractErrorMessage(
            payload,
            `Unable to save Odoo connection (${response.status})`,
          ),
        );
      }
      setConnections((prev) => {
        const next = prev.filter((item) => item.id !== payload.id);
        return [payload, ...next];
      });
      await assignConnection(payload.id);
    } catch (nextError: any) {
      setConnectionError(
        nextError?.message || "Unable to save the Odoo connection.",
      );
    } finally {
      setConnectionSaving(false);
    }
  };

  const runSync = async () => {
    setSyncing(true);
    setConnectionError(null);
    setConnectionSuccess(null);
    try {
      const response = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/odoo/sync/${auditId}`,
        { method: "POST" },
      );
      const raw = await response.text();
      const payload = raw ? parseJson<any>(raw) : {};
      if (!response.ok) {
        throw new Error(
          extractErrorMessage(
            payload,
            `Unable to sync Odoo records (${response.status})`,
          ),
        );
      }
      setSyncSummary(payload.summary || {});
      setConnectionSuccess("Odoo content sync completed.");
      await loadPlan();
    } catch (nextError: any) {
      setConnectionError(nextError?.message || "Unable to sync Odoo records.");
    } finally {
      setSyncing(false);
    }
  };

  const prepareDraftPack = async () => {
    setPreparingDrafts(true);
    setConnectionError(null);
    setConnectionSuccess(null);
    try {
      const response = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/odoo/drafts/${auditId}/prepare`,
        { method: "POST" },
      );
      const raw = await response.text();
      const payload = raw ? parseJson<any>(raw) : {};
      if (!response.ok) {
        throw new Error(
          extractErrorMessage(
            payload,
            `Unable to prepare Odoo drafts (${response.status})`,
          ),
        );
      }
      setDrafts(payload);
      setConnectionSuccess("Draft pack prepared from the current Odoo sync.");
      await loadPlan();
    } catch (nextError: any) {
      setConnectionError(
        nextError?.message || "Unable to prepare Odoo drafts.",
      );
    } finally {
      setPreparingDrafts(false);
    }
  };

  const updateInputValue = (
    groupId: string,
    fieldKey: string,
    value: string,
  ) => {
    setInputValues((prev) => ({
      ...prev,
      [groupId]: {
        ...(prev[groupId] || {}),
        [fieldKey]: value,
      },
    }));
  };

  const fetchFixSuggestion = useCallback(
    async (step: FixChatStep, index: number) => {
      setChatSteps((prev) =>
        prev.map((item, itemIndex) =>
          itemIndex === index ? { ...item, loading: true } : item,
        ),
      );
      try {
        const response = await fetchWithBackendAuth(
          `${backendUrl}/api/v1/odoo/delivery-fix-inputs/chat/${auditId}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              issue_code: step.issueCode,
              field_key: step.field.key,
              field_label: step.field.label,
              placeholder: step.field.placeholder,
              current_values: inputValues[step.groupId] || {},
              language: briefDraft.language || "en",
              history: [],
            }),
          },
        );
        const raw = await response.text();
        const payload = raw
          ? parseJson<FixInputChatResponse>(raw)
          : {
              assistant_message: "",
              suggested_value: "",
              confidence: "unknown",
            };
        if (response.ok) {
          setChatSteps((prev) =>
            prev.map((item, itemIndex) =>
              itemIndex === index
                ? {
                    ...item,
                    loading: false,
                    assistantMessage: payload.assistant_message,
                    suggestedValue: payload.suggested_value,
                    confidence: payload.confidence,
                  }
                : item,
            ),
          );
          return;
        }
      } catch (nextError) {
        console.error("Error fetching Odoo fix suggestion:", nextError);
      }
      setChatSteps((prev) =>
        prev.map((item, itemIndex) =>
          itemIndex === index
            ? {
                ...item,
                loading: false,
                assistantMessage:
                  "Please provide the requested value using approved site content and audit evidence only.",
                suggestedValue: "",
                confidence: "unknown",
              }
            : item,
        ),
      );
    },
    [auditId, backendUrl, briefDraft.language, inputValues],
  );

  useEffect(() => {
    if (
      !activeFixStep ||
      activeFixStep.assistantMessage ||
      activeFixStep.loading
    ) {
      return;
    }
    void fetchFixSuggestion(activeFixStep, currentFixStepIndex);
  }, [activeFixStep, currentFixStepIndex, fetchFixSuggestion]);

  const handleUseSuggestion = (step: FixChatStep) => {
    if (!step.suggestedValue) return;
    updateInputValue(step.groupId, step.field.key, step.suggestedValue);
    setStepError(null);
  };

  const handleNextFixStep = (step: FixChatStep) => {
    const value = (inputValues[step.groupId]?.[step.field.key] || "").trim();
    if (step.required && !value) {
      setStepError(
        "This field is required to finalize the Odoo delivery pack.",
      );
      return;
    }
    setStepError(null);
    setCurrentFixStepIndex((prev) =>
      prev >= chatSteps.length - 1 ? chatSteps.length : prev + 1,
    );
  };

  const buildInputsPayload = () =>
    missingInputs.map((group) => {
      const values: Record<string, any> = {};
      const groupValues = inputValues[group.id] || {};
      group.fields.forEach((field) => {
        values[field.key] = groupValues[field.key] ?? "";
      });
      if (group.issue_code?.toUpperCase().startsWith("FAQ_")) {
        const faqItems: Array<{ question: string; answer: string }> = [];
        for (let index = 1; index <= 3; index += 1) {
          const question = (values[`faq_q${index}`] || "").toString().trim();
          const answer = (values[`faq_a${index}`] || "").toString().trim();
          if (question || answer) faqItems.push({ question, answer });
        }
        return {
          id: group.id,
          issue_code: group.issue_code,
          page_path: group.page_path,
          values: { faq_items: faqItems },
        };
      }
      return {
        id: group.id,
        issue_code: group.issue_code,
        page_path: group.page_path,
        values,
      };
    });

  const saveFixInputs = async () => {
    setInputsSaving(true);
    setFixSuccess(null);
    setStepError(null);
    try {
      const response = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/odoo/delivery-fix-inputs/${auditId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ inputs: buildInputsPayload() }),
        },
      );
      const raw = await response.text();
      const payload = raw ? parseJson<FixInputsResponse | any>(raw) : {};
      if (!response.ok) {
        throw new Error(
          payload?.detail ||
            `Unable to save implementation inputs (${response.status})`,
        );
      }
      setMissingInputs(payload.missing_inputs || []);
      await loadPlan();
      setFixSuccess("Implementation inputs saved and pack refreshed.");
      startTransition(() => {
        router.refresh();
      });
    } catch (nextError: any) {
      setStepError(
        nextError?.message || "Unable to save implementation inputs.",
      );
    } finally {
      setInputsSaving(false);
    }
  };

  const hasMissingRequired = missingInputs.some((group) => group.required);
  const draftSummary = drafts.summary || {};
  const connectionWarnings = selectedConnection?.warnings || [];
  const syncModelEntries = Object.entries(syncSummary.counts_by_model || {});
  const briefSummaryItems = [
    { label: "Primary goal", value: briefDraft.primary_goal || "Not set" },
    { label: "Market", value: briefDraft.market || "Not set" },
    { label: "Language", value: formatLanguage(briefDraft.language) },
    {
      label: "Articles",
      value: supportsArticles
        ? briefDraft.add_articles
          ? "Included"
          : "Excluded"
        : "Not available",
    },
    {
      label: "Ecommerce fixes",
      value: supportsEcommerce
        ? briefDraft.improve_ecommerce_fixes
          ? "Included"
          : "Excluded"
        : "Not applicable",
    },
    { label: "Owner", value: briefDraft.team_owner || "Not set" },
  ];

  return (
    <div className="min-h-screen bg-background pb-20 text-foreground">
      <Header />
      <main className="mx-auto flex max-w-7xl flex-col gap-8 px-6 py-10">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <Button
              asChild
              variant="ghost"
              className="mb-6 pl-0 text-muted-foreground"
            >
              <Link href={auditDetailHref}>
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Audit Summary
              </Link>
            </Button>
            <div className="flex items-center gap-3">
              <div className="rounded-2xl bg-emerald-500/15 p-3">
                <Package className="h-7 w-7 text-emerald-600" />
              </div>
              <div>
                <h1 className="text-3xl font-semibold md:text-4xl">
                  Odoo Delivery Pack
                </h1>
                <p className="mt-2 max-w-3xl text-muted-foreground">
                  Client-facing Odoo implementation workspace with guided
                  briefing, missing-input collection, and a grounded delivery
                  pack.
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Badge variant="outline">Audit {auditId}</Badge>
            {isEcommerce ? (
              <Badge variant="outline">Ecommerce detected</Badge>
            ) : null}
            <Button
              onClick={() => void loadPlan()}
              variant="outline"
              disabled={refreshing}
            >
              {refreshing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Refresh Pack
            </Button>
            <Button onClick={copyPacket} variant="outline">
              <Clipboard className="mr-2 h-4 w-4" />
              {copied ? "Copied" : "Copy Pack"}
            </Button>
          </div>
        </div>

        {error ? (
          <Card className="border-amber-500/30 bg-amber-500/5">
            <CardHeader>
              <CardTitle>Delivery pack unavailable</CardTitle>
              <CardDescription>{error}</CardDescription>
            </CardHeader>
          </Card>
        ) : null}

        {connectionError ? (
          <Card className="border-amber-500/30 bg-amber-500/5">
            <CardHeader>
              <CardTitle>Odoo integration issue</CardTitle>
              <CardDescription>{connectionError}</CardDescription>
            </CardHeader>
          </Card>
        ) : null}

        {connectionSuccess ? (
          <Card className="border-emerald-500/30 bg-emerald-500/5">
            <CardHeader>
              <CardTitle>Odoo integration updated</CardTitle>
              <CardDescription>{connectionSuccess}</CardDescription>
            </CardHeader>
          </Card>
        ) : null}

        {plan ? (
          <>
            <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <Package className="h-5 w-5 text-emerald-600" />
                    <div>
                      <CardTitle>Connection</CardTitle>
                      <CardDescription>
                        Connect a real Odoo instance with URL, database, email,
                        and API key. This tool does not touch PageSpeed,
                        infrastructure, or live templates.
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <p className="text-sm font-medium">URL</p>
                      <Input
                        value={connectionDraft.base_url}
                        onChange={(event) =>
                          updateConnectionField("base_url", event.target.value)
                        }
                        placeholder="https://your-odoo.example.com"
                      />
                    </div>
                    <div className="space-y-2">
                      <p className="text-sm font-medium">Database</p>
                      <Input
                        value={connectionDraft.database}
                        onChange={(event) =>
                          updateConnectionField("database", event.target.value)
                        }
                        placeholder="odoo-prod"
                      />
                    </div>
                    <div className="space-y-2">
                      <p className="text-sm font-medium">Email</p>
                      <Input
                        value={connectionDraft.email}
                        onChange={(event) =>
                          updateConnectionField("email", event.target.value)
                        }
                        placeholder="team@client.com"
                      />
                    </div>
                    <div className="space-y-2">
                      <p className="text-sm font-medium">API key</p>
                      <Input
                        type="password"
                        value={connectionDraft.api_key}
                        onChange={(event) =>
                          updateConnectionField("api_key", event.target.value)
                        }
                        placeholder="Paste Odoo API key"
                      />
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <Button
                      variant="outline"
                      onClick={() => void testConnection()}
                      disabled={connectionTesting}
                    >
                      {connectionTesting ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <CheckCircle2 className="mr-2 h-4 w-4" />
                      )}
                      Test connection
                    </Button>
                    <Button
                      onClick={() => void saveAndConnect()}
                      disabled={connectionSaving}
                    >
                      {connectionSaving ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <SendHorizontal className="mr-2 h-4 w-4" />
                      )}
                      Save and connect
                    </Button>
                  </div>

                  {connections.length > 0 ? (
                    <div className="space-y-3">
                      <p className="text-sm font-medium">Saved connections</p>
                      <div className="grid gap-3">
                        {connections.map((connection) => {
                          const isSelected =
                            selectedConnection?.id === connection.id;
                          return (
                            <div
                              key={connection.id}
                              className="rounded-2xl border border-border/70 bg-muted/30 p-4"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                  <p className="font-medium">
                                    {connection.label || connection.base_url}
                                  </p>
                                  <p className="mt-1 text-xs text-muted-foreground">
                                    {connection.base_url} ·{" "}
                                    {connection.database}
                                    {connection.odoo_version
                                      ? ` · ${connection.odoo_version}`
                                      : ""}
                                  </p>
                                </div>
                                <Button
                                  variant={isSelected ? "secondary" : "outline"}
                                  onClick={() =>
                                    void assignConnection(connection.id)
                                  }
                                  disabled={
                                    assigningConnectionId === connection.id
                                  }
                                >
                                  {assigningConnectionId === connection.id ? (
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                  ) : null}
                                  {isSelected ? "Connected" : "Use connection"}
                                </Button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ) : null}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <Layers3 className="h-5 w-5 text-brand" />
                    <div>
                      <CardTitle>Connection Status</CardTitle>
                      <CardDescription>
                        Safe Odoo rollout only. No `ir.ui.view`, no layout
                        writes, no infrastructure changes.
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4 text-sm">
                  <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      Selected connection
                    </p>
                    <p className="mt-2 font-medium">
                      {selectedConnection?.label ||
                        plan.connection_status?.message ||
                        "No Odoo connection selected yet."}
                    </p>
                    {selectedConnection ? (
                      <p className="mt-2 text-muted-foreground">
                        {selectedConnection.base_url} ·{" "}
                        {selectedConnection.database}
                        {selectedConnection.detected_user?.email
                          ? ` · ${selectedConnection.detected_user.email}`
                          : ""}
                      </p>
                    ) : null}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">
                        Capabilities
                      </p>
                      <p className="mt-2 text-sm">
                        Website {capabilities.website ? "on" : "off"} · Blog{" "}
                        {supportsArticles ? "on" : "off"} · Ecommerce{" "}
                        {supportsEcommerce ? "on" : "off"}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">
                        Sync status
                      </p>
                      <p className="mt-2 text-sm">
                        {syncSummary.status || "not_synced"} · mapped{" "}
                        {syncSummary.mapped_count ?? 0} · unmapped{" "}
                        {syncSummary.unmapped_count ?? 0}
                      </p>
                    </div>
                  </div>
                  {connectionWarnings.length > 0 ? (
                    <div className="space-y-2">
                      {connectionWarnings.map((warning) => (
                        <div
                          key={warning}
                          className="flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4"
                        >
                          <AlertCircle className="mt-0.5 h-4 w-4 text-amber-500" />
                          <p>{warning}</p>
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {(plan.blocked_scope || []).map((item) => (
                    <div
                      key={item}
                      className="flex items-start gap-3 rounded-2xl border border-border/70 bg-muted/30 p-4"
                    >
                      <AlertCircle className="mt-0.5 h-4 w-4 text-muted-foreground" />
                      <p>{item}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>

            {!hasSelectedConnection ? (
              <Card className="border-sky-500/30 bg-sky-500/5">
                <CardHeader>
                  <CardTitle>Select an Odoo connection to continue</CardTitle>
                  <CardDescription>
                    The Odoo GeoTool starts with a real instance connection.
                    Once a connection is attached to this audit, the briefing,
                    sync, and draft pack blocks unlock below.
                  </CardDescription>
                </CardHeader>
              </Card>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <Card>
                    <CardHeader>
                      <CardDescription>Validated fixes</CardDescription>
                      <CardTitle className="text-3xl">
                        {plan.delivery_summary?.fix_count ?? 0}
                      </CardTitle>
                    </CardHeader>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardDescription>Article deliverables</CardDescription>
                      <CardTitle className="text-3xl">
                        {plan.delivery_summary?.article_count ?? 0}
                      </CardTitle>
                    </CardHeader>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardDescription>Native drafts</CardDescription>
                      <CardTitle className="text-3xl">
                        {draftSummary.native_draft_count ??
                          plan.delivery_summary?.native_draft_count ??
                          0}
                      </CardTitle>
                    </CardHeader>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardDescription>Manual review items</CardDescription>
                      <CardTitle className="text-3xl">
                        {draftSummary.manual_review_count ??
                          plan.delivery_summary?.manual_review_count ??
                          0}
                      </CardTitle>
                    </CardHeader>
                  </Card>
                </div>

                <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
                  <Card>
                    <CardHeader>
                      <div className="flex items-center gap-3">
                        <MessageSquareText className="h-5 w-5 text-sky-500" />
                        <div>
                          <CardTitle>Guided Odoo Briefing</CardTitle>
                          <CardDescription>
                            Conversational setup for scope, market, content, and
                            ecommerce decisions.
                          </CardDescription>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-5">
                      <div className="rounded-2xl border border-sky-500/20 bg-sky-500/5 p-4 text-sm text-muted-foreground">
                        <div className="flex items-start gap-3">
                          <Bot className="mt-0.5 h-4 w-4 text-sky-500" />
                          <p>{briefingIntro}</p>
                        </div>
                      </div>

                      {activeBriefStep ? (
                        <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                          <div className="flex items-start gap-3">
                            <Bot className="mt-0.5 h-4 w-4 text-sky-500" />
                            <div className="min-w-0 flex-1 space-y-4">
                              <div>
                                <p className="text-sm font-medium">
                                  {activeBriefStep.label}
                                </p>
                                <p className="mt-2 text-sm text-muted-foreground">
                                  {activeBriefStep.assistantMessage}
                                </p>
                              </div>
                              {activeBriefStep.type === "choice" ? (
                                <div className="grid gap-3 md:grid-cols-2">
                                  {(activeBriefStep.options || []).map(
                                    (option) => (
                                      <button
                                        type="button"
                                        key={`${activeBriefStep.id}-${option.value}`}
                                        onClick={() =>
                                          handleBriefChoice(option)
                                        }
                                        className="rounded-2xl border border-border/70 bg-background/70 p-4 text-left transition hover:border-sky-500/40 hover:bg-sky-500/5"
                                      >
                                        <p className="font-medium">
                                          {option.label}
                                        </p>
                                        <p className="mt-2 text-sm text-muted-foreground">
                                          {option.description}
                                        </p>
                                      </button>
                                    ),
                                  )}
                                </div>
                              ) : (
                                <div className="space-y-3">
                                  {activeBriefStep.type === "textarea" ? (
                                    <Textarea
                                      value={briefInputValue}
                                      onChange={(event) =>
                                        setBriefInputValue(event.target.value)
                                      }
                                      placeholder={activeBriefStep.placeholder}
                                    />
                                  ) : (
                                    <Input
                                      value={briefInputValue}
                                      onChange={(event) =>
                                        setBriefInputValue(event.target.value)
                                      }
                                      placeholder={activeBriefStep.placeholder}
                                    />
                                  )}
                                  <div className="flex flex-wrap gap-3">
                                    <Button
                                      onClick={() => submitBriefTextStep(false)}
                                    >
                                      <SendHorizontal className="mr-2 h-4 w-4" />
                                      Save answer
                                    </Button>
                                    {!activeBriefStep.required ? (
                                      <Button
                                        variant="outline"
                                        onClick={() =>
                                          submitBriefTextStep(true)
                                        }
                                      >
                                        Skip
                                      </Button>
                                    ) : null}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-sm text-muted-foreground">
                          Brief complete. Apply it now or restart the chat if
                          you want to reshape the rollout.
                        </div>
                      )}

                      {briefError ? (
                        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm">
                          {briefError}
                        </div>
                      ) : null}
                      {briefSuccess ? (
                        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-4 text-sm">
                          {briefSuccess}
                        </div>
                      ) : null}

                      <div className="flex flex-wrap gap-3">
                        <Button
                          onClick={() => void saveBriefing()}
                          disabled={briefSaving}
                        >
                          {briefSaving ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          ) : (
                            <CheckCircle2 className="mr-2 h-4 w-4" />
                          )}
                          Apply brief and refresh pack
                        </Button>
                        <Button variant="outline" onClick={restartBriefing}>
                          Restart chat
                        </Button>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <div className="flex items-center gap-3">
                        <Layers3 className="h-5 w-5 text-brand" />
                        <div>
                          <CardTitle>Current Brief</CardTitle>
                          <CardDescription>
                            Live briefing state for the client-facing pack.
                          </CardDescription>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="grid gap-3 sm:grid-cols-2">
                      {briefSummaryItems.map((item) => (
                        <div
                          key={item.label}
                          className="rounded-2xl border border-border/70 bg-muted/30 p-4"
                        >
                          <p className="text-xs uppercase tracking-wide text-muted-foreground">
                            {item.label}
                          </p>
                          <p className="mt-2 text-sm font-medium">
                            {item.value}
                          </p>
                        </div>
                      ))}
                      <div className="rounded-2xl border border-border/70 bg-muted/30 p-4 sm:col-span-2">
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">
                          Rollout notes
                        </p>
                        <p className="mt-2 text-sm text-muted-foreground">
                          {briefDraft.rollout_notes ||
                            "No extra constraints captured yet."}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                </div>

                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <UserRound className="h-5 w-5 text-amber-500" />
                      <div>
                        <CardTitle>Guided Implementation Inputs</CardTitle>
                        <CardDescription>
                          Complete missing validated values before treating the
                          pack as implementation-final.
                        </CardDescription>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {activeFixStep ? (
                      <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                        <div className="flex items-start gap-3">
                          <Bot className="mt-0.5 h-4 w-4 text-amber-500" />
                          <div className="min-w-0 flex-1 space-y-4">
                            <div className="flex flex-wrap items-center gap-3">
                              <p className="text-sm font-medium">
                                {activeFixStep.issueCode} ·{" "}
                                {activeFixStep.pagePath}
                              </p>
                              <Badge variant="outline">
                                {activeFixStep.required
                                  ? "Required"
                                  : "Optional"}
                              </Badge>
                              <Badge variant="outline">
                                {currentFixStepIndex + 1}/{chatSteps.length}
                              </Badge>
                            </div>
                            {activeFixStep.prompt ? (
                              <p className="text-sm text-muted-foreground">
                                {activeFixStep.prompt}
                              </p>
                            ) : null}
                            {activeFixStep.loading ? (
                              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                Preparing grounded suggestion...
                              </div>
                            ) : activeFixStep.assistantMessage ? (
                              <div className="rounded-2xl border border-border/70 bg-background/70 p-4 text-sm text-muted-foreground">
                                {activeFixStep.assistantMessage}
                              </div>
                            ) : null}
                            {activeFixStep.field.input_type === "textarea" ? (
                              <Textarea
                                value={
                                  inputValues[activeFixStep.groupId]?.[
                                    activeFixStep.field.key
                                  ] || ""
                                }
                                onChange={(event) =>
                                  updateInputValue(
                                    activeFixStep.groupId,
                                    activeFixStep.field.key,
                                    event.target.value,
                                  )
                                }
                                placeholder={activeFixStep.field.placeholder}
                              />
                            ) : (
                              <Input
                                value={
                                  inputValues[activeFixStep.groupId]?.[
                                    activeFixStep.field.key
                                  ] || ""
                                }
                                onChange={(event) =>
                                  updateInputValue(
                                    activeFixStep.groupId,
                                    activeFixStep.field.key,
                                    event.target.value,
                                  )
                                }
                                placeholder={activeFixStep.field.placeholder}
                              />
                            )}
                            <div className="flex flex-wrap gap-3">
                              {activeFixStep.suggestedValue ? (
                                <Button
                                  variant="outline"
                                  onClick={() =>
                                    handleUseSuggestion(activeFixStep)
                                  }
                                >
                                  Use suggestion
                                  {activeFixStep.confidence === "evidence"
                                    ? " (grounded)"
                                    : ""}
                                </Button>
                              ) : null}
                              <Button
                                onClick={() => handleNextFixStep(activeFixStep)}
                              >
                                Next field
                              </Button>
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-sm text-muted-foreground">
                        No implementation inputs are missing right now.
                      </div>
                    )}
                    {stepError ? (
                      <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm">
                        {stepError}
                      </div>
                    ) : null}
                    {fixSuccess ? (
                      <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-4 text-sm">
                        {fixSuccess}
                      </div>
                    ) : null}
                    <div className="flex flex-wrap gap-3">
                      <Button
                        onClick={() => void saveFixInputs()}
                        disabled={inputsSaving}
                      >
                        {inputsSaving ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <CheckCircle2 className="mr-2 h-4 w-4" />
                        )}
                        Save implementation inputs
                      </Button>
                      <Badge variant="outline">
                        {hasMissingRequired
                          ? "Required fields pending"
                          : "Required fields complete"}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>

                <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
                  <Card>
                    <CardHeader>
                      <CardTitle>
                        {plan.implementation_packet?.title ||
                          "Odoo delivery pack"}
                      </CardTitle>
                      <CardDescription>
                        {plan.implementation_packet?.summary}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4 text-sm">
                      <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">
                          Branch suggestion
                        </p>
                        <p className="mt-2 font-mono">
                          {plan.implementation_packet?.branch_name_suggestion ||
                            "odoo/delivery"}
                        </p>
                      </div>
                      <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">
                          Root snapshot
                        </p>
                        <p className="mt-2 font-medium">
                          {plan.root_page_snapshot?.path || "/"}
                        </p>
                        <p className="mt-3 text-muted-foreground">
                          Overall{" "}
                          {plan.root_page_snapshot?.overall_score ?? "n/a"} ·
                          Schema{" "}
                          {plan.root_page_snapshot?.schema_score ?? "n/a"} · H1{" "}
                          {plan.root_page_snapshot?.h1_score ?? "n/a"}
                        </p>
                      </div>
                      {(plan.implementation_packet?.success_metrics || []).map(
                        (item) => (
                          <div
                            key={item}
                            className="flex items-start gap-3 rounded-2xl border border-border/70 bg-muted/30 p-4"
                          >
                            <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500" />
                            <p>{item}</p>
                          </div>
                        ),
                      )}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>QA Checklist</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {(plan.qa_checklist || []).map((item) => (
                        <div
                          key={item}
                          className="flex items-start gap-3 rounded-2xl border border-border/70 bg-muted/30 p-4"
                        >
                          <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500" />
                          <p className="text-sm">{item}</p>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle>Odoo Delivery Fixes</CardTitle>
                    <CardDescription>
                      Validated fixes from the audit fix plan, excluding
                      infrastructure-only work.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {(plan.odoo_ready_fixes || []).map((item) => (
                      <div
                        key={`${item.issue_code}-${item.page_path}-${item.area}`}
                        className="rounded-2xl border border-border/70 bg-muted/30 p-4"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="font-medium">{item.area || "Fix"}</p>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {item.page_path || "/"}
                            </p>
                          </div>
                          <Badge variant="outline">
                            {item.priority || "MEDIUM"}
                          </Badge>
                        </div>
                        <p className="mt-3 text-sm">{item.what_to_change}</p>
                        <p className="mt-2 text-xs text-muted-foreground">
                          Surface: {item.recommended_odoo_surface}
                        </p>
                        <p className="mt-2 text-xs text-muted-foreground">
                          Why: {item.why_it_matters}
                        </p>
                        <p className="mt-2 text-xs text-muted-foreground">
                          QA: {item.qa_check}
                        </p>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                {(plan.article_deliverables || []).length > 0 ? (
                  <Card>
                    <CardHeader>
                      <div className="flex items-center gap-3">
                        <FileText className="h-5 w-5 text-indigo-500" />
                        <div>
                          <CardTitle>Article Deliverables</CardTitle>
                          <CardDescription>
                            Content pieces to publish from Odoo blog and link
                            back to commercial pages.
                          </CardDescription>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {(plan.article_deliverables || []).map((item) => (
                        <div
                          key={`${item.slug}-${item.title}`}
                          className="rounded-2xl border border-border/70 bg-muted/30 p-4"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <p className="font-medium">{item.title}</p>
                              <p className="mt-1 text-xs text-muted-foreground">
                                keyword: {item.target_keyword || "n/a"} · focus:{" "}
                                {item.focus_url || "/"}
                              </p>
                            </div>
                            <Badge variant="outline">
                              {item.source === "article_engine_batch"
                                ? "Generated"
                                : "Suggested"}
                            </Badge>
                          </div>
                          <p className="mt-3 text-sm">{item.delivery_brief}</p>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                ) : null}

                {(plan.ecommerce_fixes || []).length > 0 || isEcommerce ? (
                  <Card>
                    <CardHeader>
                      <div className="flex items-center gap-3">
                        <ShoppingBag className="h-5 w-5 text-emerald-500" />
                        <div>
                          <CardTitle>Ecommerce Delivery Block</CardTitle>
                          <CardDescription>
                            Product, category, and homepage actions for Odoo
                            ecommerce implementations.
                          </CardDescription>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {plan.commerce_context?.has_analysis ? (
                        <div className="rounded-2xl border border-border/70 bg-muted/30 p-4 text-sm text-muted-foreground">
                          Query context: {plan.commerce_context.query || "n/a"}{" "}
                          · market {plan.commerce_context.market || "n/a"} ·
                          target position{" "}
                          {plan.commerce_context.target_position ?? "n/a"} · top
                          result{" "}
                          {plan.commerce_context.top_result_domain || "n/a"}
                        </div>
                      ) : null}
                      {(plan.commerce_root_causes || []).map((item, index) => (
                        <div
                          key={`${item.title}-${index}`}
                          className="rounded-2xl border border-border/70 bg-muted/30 p-4"
                        >
                          <p className="font-medium">{item.title}</p>
                          <p className="mt-2 text-sm text-muted-foreground">
                            {item.finding}
                          </p>
                        </div>
                      ))}
                      {(plan.ecommerce_fixes || []).map((item, index) => (
                        <div
                          key={`${item.area}-${index}-${item.what_to_change}`}
                          className="rounded-2xl border border-border/70 bg-muted/30 p-4"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-medium">
                              {item.area || "Ecommerce"}
                            </p>
                            <Badge variant="outline">
                              {item.priority || "P2"}
                            </Badge>
                          </div>
                          <p className="mt-3 text-sm">{item.what_to_change}</p>
                          <p className="mt-2 text-xs text-muted-foreground">
                            Surface: {item.recommended_odoo_surface}
                          </p>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                ) : null}

                <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
                  <Card>
                    <CardHeader>
                      <CardTitle>Sync</CardTitle>
                      <CardDescription>
                        Pull real Odoo records before preparing drafts. This
                        reads content only and never writes templates or
                        infrastructure.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="flex flex-wrap gap-3">
                        <Button
                          onClick={() => void runSync()}
                          disabled={syncing}
                        >
                          {syncing ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          ) : (
                            <RefreshCw className="mr-2 h-4 w-4" />
                          )}
                          Sync Odoo content
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => void prepareDraftPack()}
                          disabled={preparingDrafts}
                        >
                          {preparingDrafts ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          ) : (
                            <Package className="mr-2 h-4 w-4" />
                          )}
                          Prepare draft pack
                        </Button>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                          <p className="text-xs uppercase tracking-wide text-muted-foreground">
                            Mapped audit URLs
                          </p>
                          <p className="mt-2 text-2xl font-semibold">
                            {syncSummary.mapped_count ?? 0}
                          </p>
                        </div>
                        <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                          <p className="text-xs uppercase tracking-wide text-muted-foreground">
                            Unmapped URLs
                          </p>
                          <p className="mt-2 text-2xl font-semibold">
                            {syncSummary.unmapped_count ?? 0}
                          </p>
                        </div>
                      </div>
                      {syncModelEntries.length > 0 ? (
                        <div className="space-y-2">
                          {syncModelEntries.map(([model, count]) => (
                            <div
                              key={model}
                              className="flex items-center justify-between rounded-2xl border border-border/70 bg-muted/30 px-4 py-3 text-sm"
                            >
                              <span>{model}</span>
                              <Badge variant="outline">{count}</Badge>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="rounded-2xl border border-border/70 bg-muted/30 p-4 text-sm text-muted-foreground">
                          No Odoo records have been synced for this audit yet.
                        </div>
                      )}
                      {(syncSummary.unmapped_paths || [])
                        .slice(0, 6)
                        .map((path) => (
                          <div
                            key={path}
                            className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm"
                          >
                            Unmapped audit path: {path}
                          </div>
                        ))}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Draft Pack</CardTitle>
                      <CardDescription>
                        Native drafts in Odoo when supported, structured draft
                        actions for safe fields, and manual review for
                        template-backed work.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                          <p className="text-xs uppercase tracking-wide text-muted-foreground">
                            Native drafts
                          </p>
                          <p className="mt-2 text-2xl font-semibold">
                            {draftSummary.native_draft_count ?? 0}
                          </p>
                        </div>
                        <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                          <p className="text-xs uppercase tracking-wide text-muted-foreground">
                            Structured drafts
                          </p>
                          <p className="mt-2 text-2xl font-semibold">
                            {draftSummary.draft_count ?? 0}
                          </p>
                        </div>
                        <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                          <p className="text-xs uppercase tracking-wide text-muted-foreground">
                            Manual review
                          </p>
                          <p className="mt-2 text-2xl font-semibold">
                            {draftSummary.manual_review_count ?? 0}
                          </p>
                        </div>
                        <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                          <p className="text-xs uppercase tracking-wide text-muted-foreground">
                            Failed
                          </p>
                          <p className="mt-2 text-2xl font-semibold">
                            {draftSummary.failed_count ?? 0}
                          </p>
                        </div>
                      </div>

                      {drafts.native_created.map((item) => (
                        <div
                          key={item.id}
                          className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4"
                        >
                          <p className="font-medium">
                            {item.title || "Native Odoo draft"}
                          </p>
                          <p className="mt-2 text-sm text-muted-foreground">
                            {item.target_model}{" "}
                            {item.external_record_id
                              ? `· record ${item.external_record_id}`
                              : ""}
                          </p>
                        </div>
                      ))}
                      {drafts.draft.map((item) => (
                        <div
                          key={item.id}
                          className="rounded-2xl border border-border/70 bg-muted/30 p-4"
                        >
                          <p className="font-medium">
                            {item.title || "Draft action"}
                          </p>
                          <p className="mt-2 text-sm text-muted-foreground">
                            {item.target_model || "Draft"} ·{" "}
                            {item.target_path || "/"}
                          </p>
                        </div>
                      ))}
                      {drafts.manual_review.map((item) => (
                        <div
                          key={item.id}
                          className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4"
                        >
                          <p className="font-medium">
                            {item.title || "Manual review"}
                          </p>
                          <p className="mt-2 text-sm text-muted-foreground">
                            {item.acceptance_criteria ||
                              "Review manually inside Odoo."}
                          </p>
                        </div>
                      ))}
                      {drafts.failed.map((item) => (
                        <div
                          key={item.id}
                          className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4"
                        >
                          <p className="font-medium">
                            {item.title || "Failed draft"}
                          </p>
                          <p className="mt-2 text-sm text-muted-foreground">
                            {item.error_message || "Draft generation failed."}
                          </p>
                        </div>
                      ))}

                      {drafts.native_created.length === 0 &&
                      drafts.draft.length === 0 &&
                      drafts.manual_review.length === 0 &&
                      drafts.failed.length === 0 ? (
                        <div className="rounded-2xl border border-border/70 bg-muted/30 p-4 text-sm text-muted-foreground">
                          No Odoo drafts prepared yet. Run sync first, then
                          prepare the draft pack.
                        </div>
                      ) : null}
                    </CardContent>
                  </Card>
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle>Notes</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm text-muted-foreground">
                    {(plan.notes || []).map((item) => (
                      <p key={item}>{item}</p>
                    ))}
                    {plan.product_intelligence?.is_ecommerce ? (
                      <p>
                        Product intelligence: platform{" "}
                        {plan.product_intelligence.platform || "unknown"} ·
                        product pages{" "}
                        {plan.product_intelligence.product_pages_count ?? "n/a"}{" "}
                        · category pages{" "}
                        {plan.product_intelligence.category_pages_count ??
                          "n/a"}
                      </p>
                    ) : null}
                  </CardContent>
                </Card>
              </>
            )}
          </>
        ) : null}
      </main>
    </div>
  );
}
