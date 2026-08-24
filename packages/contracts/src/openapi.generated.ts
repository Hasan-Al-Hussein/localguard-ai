export interface paths {
    "/approvals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Approvals */
        get: operations["list_approvals_approvals_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/approvals/{proposal_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Approval */
        get: operations["get_approval_approvals__proposal_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/approvals/{proposal_id}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Approve Proposal */
        post: operations["approve_proposal_approvals__proposal_id__approve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/approvals/{proposal_id}/edit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Edit Proposal */
        post: operations["edit_proposal_approvals__proposal_id__edit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/approvals/{proposal_id}/reject": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reject Proposal */
        post: operations["reject_proposal_approvals__proposal_id__reject_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/audit-events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Audit Events */
        get: operations["list_audit_events_audit_events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/audit-events/{event_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Audit Event */
        get: operations["get_audit_event_audit_events__event_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/csrf": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Csrf */
        get: operations["csrf_auth_csrf_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Me */
        get: operations["me_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/documents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Documents */
        get: operations["list_documents_documents_get"];
        put?: never;
        /** Upload Document */
        post: operations["upload_document_documents_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/documents/{document_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Document */
        get: operations["get_document_documents__document_id__get"];
        put?: never;
        post?: never;
        /** Delete Document */
        delete: operations["delete_document_documents__document_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/documents/{document_id}/pages/{page}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Document Page */
        get: operations["get_document_page_documents__document_id__pages__page__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/documents/{document_id}/reprocess": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reprocess Document */
        post: operations["reprocess_document_documents__document_id__reprocess_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/documents/{document_id}/revisions/{revision_id}/anchors/{anchor_key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Revision Section */
        get: operations["get_revision_section_documents__document_id__revisions__revision_id__anchors__anchor_key__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/evaluations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Evaluations */
        get: operations["list_evaluations_evaluations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/evaluations/latest": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Latest Evaluation */
        get: operations["latest_evaluation_evaluations_latest_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/evaluations/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Evaluation */
        get: operations["get_evaluation_evaluations__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/findings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Findings */
        get: operations["list_findings_findings_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/live": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health Live */
        get: operations["health_live_health_live_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health Ready */
        get: operations["health_ready_health_ready_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/overview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Overview */
        get: operations["get_overview_overview_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/questions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Questions */
        get: operations["list_questions_questions_get"];
        put?: never;
        /** Create Question */
        post: operations["create_question_questions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/questions/{job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Question */
        get: operations["get_question_questions__job_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/tasks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Tasks */
        get: operations["list_tasks_tasks_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/tasks/{task_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Task */
        get: operations["get_task_tasks__task_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Task */
        patch: operations["update_task_tasks__task_id__patch"];
        trace?: never;
    };
    "/workflow-runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Workflow Run */
        post: operations["create_workflow_run_workflow_runs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workflow-runs/{thread_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Workflow Run */
        get: operations["get_workflow_run_workflow_runs__thread_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ActivitySummary */
        ActivitySummary: {
            /** Action */
            action: string;
            /** Correlation Id */
            correlation_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /** Outcome */
            outcome: string;
            /** Resource Id */
            resource_id: string | null;
            /** Resource Type */
            resource_type: string;
        };
        /** AggregateMetrics */
        AggregateMetrics: {
            approval_gate_compliance: components["schemas"]["RatioMetric"];
            approval_transition_coverage: components["schemas"]["RatioMetric"];
            /** Case Count */
            case_count: number;
            /** Citation Eligible Case Count */
            citation_eligible_case_count: number;
            citation_precision: components["schemas"]["RatioMetric"];
            /** Citation Precision Macro */
            citation_precision_macro?: number | null;
            /** Completed Case Count */
            completed_case_count: number;
            extraction: components["schemas"]["ExtractionAggregate"];
            /** Failed Case Count */
            failed_case_count: number;
            /** First Tool Confusion Matrix */
            first_tool_confusion_matrix: {
                [key: string]: {
                    [key: string]: number;
                };
            };
            forbidden_outcome_compliance: components["schemas"]["RatioMetric"];
            forbidden_outcome_control_coverage: components["schemas"]["RatioMetric"];
            grounded_retrieval: components["schemas"]["RetrievalAggregate"];
            /** Grounding Score */
            grounding_score?: number | null;
            injection_policy_compliance: components["schemas"]["RatioMetric"];
            insufficient_abstention: components["schemas"]["RatioMetric"];
            /** Latency By Stage */
            latency_by_stage: {
                [key: string]: components["schemas"]["LatencyStats"];
            };
            /** Missing Expected Claim Count */
            missing_expected_claim_count: number;
            /** Pre Approval Execution Count */
            pre_approval_execution_count: number;
            /** Pre Approval Task Count */
            pre_approval_task_count: number;
            proposal_exact_match: components["schemas"]["RatioMetric"];
            schema_validity: components["schemas"]["RatioMetric"];
            status_accuracy: components["schemas"]["RatioMetric"];
            tool_selection_accuracy: components["schemas"]["RatioMetric"];
            unsupported_claim_rate: components["schemas"]["RatioMetric"];
            /** Zero Citation Answer Count */
            zero_citation_answer_count: number;
        };
        /** AnchorPublic */
        AnchorPublic: {
            /** End Offset */
            end_offset: number;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Kind */
            kind: string;
            /** Label */
            label: string;
            /** Ordinal */
            ordinal: number;
            /** Stable Key */
            stable_key: string;
            /** Start Offset */
            start_offset: number;
            /** Text */
            text: string;
        };
        /** AnswerPublic */
        AnswerPublic: {
            /** Citations */
            citations?: components["schemas"]["CitationPublic"][];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Generation Ms */
            generation_ms: number;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Insufficient Evidence */
            insufficient_evidence: boolean;
            /** Model Name */
            model_name: string;
            /** Prompt Version */
            prompt_version: string;
            /** Retrieval Ms */
            retrieval_ms: number;
            /** Text */
            text: string;
        };
        /** ApprovalCaseMetric */
        ApprovalCaseMetric: {
            /** Compliance */
            compliance?: number | null;
            /** Compliant Transitions */
            compliant_transitions: number;
            /** Observed Transitions */
            observed_transitions: number;
            /** Pre Approval Execution Count */
            pre_approval_execution_count: number;
            /** Pre Approval Task Count */
            pre_approval_task_count: number;
            /** Tested Transitions */
            tested_transitions: number;
        };
        /**
         * ApprovalDecision
         * @enum {string}
         */
        ApprovalDecision: "approve" | "edit" | "reject" | "expire" | "replay";
        /** ApprovalObservation */
        ApprovalObservation: {
            decision: components["schemas"]["ApprovalDecision"];
            /** Payload Integrity Valid */
            payload_integrity_valid: boolean;
            proposal_status: components["schemas"]["ProposalStatus"];
            /** Step */
            step: number;
            /** Task Count */
            task_count: number;
            /** Task Ids */
            task_ids: string[];
        };
        /** ApprovalRequest */
        ApprovalRequest: {
            /** Comment */
            comment?: string | null;
            /** Evidence Snapshot Hash */
            evidence_snapshot_hash: string;
            /** Payload Hash */
            payload_hash: string;
            /** Version */
            version: number;
        };
        /** AuditEventList */
        AuditEventList: {
            /** Items */
            items: components["schemas"]["AuditEventPublic"][];
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /** Total */
            total: number;
        };
        /** AuditEventPublic */
        AuditEventPublic: {
            /** Action */
            action: string;
            /** Actor Id */
            actor_id: string | null;
            /** Causation Id */
            causation_id: string | null;
            /** Correlation Id */
            correlation_id: string;
            /** Detail */
            detail: {
                [key: string]: unknown;
            };
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /** Outcome */
            outcome: string;
            /** Resource Id */
            resource_id: string | null;
            /** Resource Type */
            resource_type: string;
            /** Thread Id */
            thread_id: string | null;
        };
        /** Body_upload_document_documents_post */
        Body_upload_document_documents_post: {
            /** File */
            file: string;
        };
        /** CSRFResponse */
        CSRFResponse: {
            /** Csrf Token */
            csrf_token: string;
        };
        /**
         * Capability
         * @enum {string}
         */
        Capability: "retrieval" | "answer" | "extraction" | "tool_trace" | "action_proposal" | "approval_resume" | "policy_observability" | "stage_latency";
        /**
         * CaseCategory
         * @enum {string}
         */
        CaseCategory: "grounded" | "insufficient" | "injection" | "action";
        /** CaseFailure */
        CaseFailure: {
            /** Code */
            code: string;
            /** Message */
            message: string;
        };
        /** CaseMetrics */
        CaseMetrics: {
            actual_first_tool: components["schemas"]["ToolName"];
            approval: components["schemas"]["ApprovalCaseMetric"];
            citation_precision: components["schemas"]["RatioMetric"];
            expected_first_tool: components["schemas"]["ToolName"];
            extraction: components["schemas"]["ExtractionCaseMetric"];
            policy: components["schemas"]["PolicyCaseMetric"];
            /** Proposal Exact */
            proposal_exact: boolean | null;
            retrieval: components["schemas"]["RetrievalCaseMetric"];
            /** Stage Latency Ms */
            stage_latency_ms: {
                [key: string]: number;
            };
            /** Status Correct */
            status_correct: boolean;
            /** Tool Sequence Exact */
            tool_sequence_exact: boolean;
            unsupported_claims: components["schemas"]["UnsupportedClaimMetric"];
        };
        /** CaseRunResult */
        CaseRunResult: {
            /** Case Id */
            case_id: string;
            category: components["schemas"]["CaseCategory"];
            failure: components["schemas"]["CaseFailure"] | null;
            metrics: components["schemas"]["CaseMetrics"] | null;
            /** Missing Capabilities */
            missing_capabilities: components["schemas"]["Capability"][];
            output: components["schemas"]["SystemCaseOutput"] | null;
            /** Provider Diagnostics */
            provider_diagnostics: components["schemas"]["ProviderCallDiagnostic"][];
            /** Task Type */
            task_type: string;
            /** Wall Clock Ms */
            wall_clock_ms: number;
        };
        /** CitationObservation */
        CitationObservation: {
            /** Marker Id */
            marker_id: string;
            /** Source Id */
            source_id: string;
        };
        /** CitationPublic */
        CitationPublic: {
            /** Anchor Key */
            anchor_key: string;
            /** Anchor Label */
            anchor_label: string;
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            /** End Offset */
            end_offset: number;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Ordinal */
            ordinal: number;
            /** Quote */
            quote: string;
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
            /** Start Offset */
            start_offset: number;
        };
        /** ClaimObservation */
        ClaimObservation: {
            /** Normalized Value */
            normalized_value: string;
            /** Predicate */
            predicate: string;
            /** Span Ids */
            span_ids: string[];
        };
        /**
         * ClaimOrigin
         * @enum {string}
         */
        ClaimOrigin: "model" | "deterministic_test_provider" | "deterministic_evidence_normalizer";
        /** ClaimProvenanceObservation */
        ClaimProvenanceObservation: {
            /** Claim Index */
            claim_index: number;
            /** Fallback Reason */
            fallback_reason?: ("duration_tuple_mismatch" | "duration_unit_agreement" | "evidence_binding_confirmed" | "evidence_binding_selected" | "performing_actor_scope" | "predicate_not_grounded" | "normalized_value_not_grounded") | null;
            /** Normalizer Version */
            normalizer_version?: ("action-obligation-v1" | "action-obligation-binding-v2" | "qa-fact-binding-v1") | null;
            origin: components["schemas"]["ClaimOrigin"];
            /** Predicate */
            predicate: string;
            /** Source Marker Sha256 */
            source_marker_sha256?: string | null;
        };
        /** ClaimProvenanceSummary */
        ClaimProvenanceSummary: {
            /** Claim Bearing Case Count */
            claim_bearing_case_count: number;
            /** Deterministic Normalizer Case Ids */
            deterministic_normalizer_case_ids: string[];
            /** Deterministic Normalizer Case Rate */
            deterministic_normalizer_case_rate: number;
            /** Deterministic Normalizer Claim Count */
            deterministic_normalizer_claim_count: number;
            /** Deterministic Test Provider Claim Count */
            deterministic_test_provider_claim_count: number;
            /** Model Claim Count */
            model_claim_count: number;
            /** Total Claim Count */
            total_claim_count: number;
        };
        /** DeadlineSummary */
        DeadlineSummary: {
            /**
             * Due Date
             * Format: date
             */
            due_date: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Severity */
            severity: string | null;
            /** Summary */
            summary: string;
            /**
             * Workflow Run Id
             * Format: uuid
             */
            workflow_run_id: string;
        };
        /** DecisionAccepted */
        DecisionAccepted: {
            decision: components["schemas"]["DecisionPublic"];
            /** Dispatch Job Id */
            dispatch_job_id: string | null;
            proposal: components["schemas"]["ProposalPublic"];
            replacement: components["schemas"]["ProposalPublic"] | null;
            task: components["schemas"]["WorkflowTaskPublic"] | null;
        };
        /**
         * DecisionKind
         * @enum {string}
         */
        DecisionKind: "approve" | "reject" | "edit";
        /** DecisionPublic */
        DecisionPublic: {
            /** Applied At */
            applied_at: string | null;
            /** Comment */
            comment: string | null;
            /**
             * Decided At
             * Format: date-time
             */
            decided_at: string;
            /**
             * Decided By Id
             * Format: uuid
             */
            decided_by_id: string;
            decision: components["schemas"]["DecisionKind"];
            /** Evidence Snapshot Hash */
            evidence_snapshot_hash: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Payload Hash */
            payload_hash: string;
            /**
             * Proposal Id
             * Format: uuid
             */
            proposal_id: string;
            /** Proposal Version */
            proposal_version: number;
            /** Replacement Proposal Id */
            replacement_proposal_id: string | null;
        };
        /** DocumentDetail */
        DocumentDetail: {
            /** Anchors */
            anchors?: components["schemas"]["AnchorPublic"][];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            current_revision?: components["schemas"]["RevisionPublic"] | null;
            /** Current Revision Id */
            current_revision_id: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            state: components["schemas"]["DocumentState"];
            /** Title */
            title: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** DocumentList */
        DocumentList: {
            /** Items */
            items: components["schemas"]["DocumentSummary"][];
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /** Total */
            total: number;
        };
        /**
         * DocumentState
         * @enum {string}
         */
        DocumentState: "queued" | "processing" | "ready" | "failed" | "deleted";
        /** DocumentSummary */
        DocumentSummary: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Current Revision Id */
            current_revision_id: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            state: components["schemas"]["DocumentState"];
            /** Title */
            title: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** EditRequest */
        EditRequest: {
            /** Assignee */
            assignee?: string | null;
            /** Comment */
            comment?: string | null;
            /** Description */
            description?: string | null;
            /** Due At */
            due_at?: string | null;
            /** Evidence Snapshot Hash */
            evidence_snapshot_hash: string;
            /** Payload Hash */
            payload_hash: string;
            priority?: components["schemas"]["TaskPriority"] | null;
            /** Reasoning Summary */
            reasoning_summary?: string | null;
            /** Title */
            title?: string | null;
            /** Version */
            version: number;
        };
        /** EvaluationHistoryDetail */
        EvaluationHistoryDetail: {
            current_run?: components["schemas"]["EvaluationRun"] | null;
            legacy_run_metadata?: components["schemas"]["LegacyEvaluationRunMetadata"] | null;
            metadata: components["schemas"]["EvaluationHistoryEntry"];
        };
        /**
         * EvaluationHistoryEntry
         * @description Schema-stable metadata; unavailable values remain explicitly null.
         */
        EvaluationHistoryEntry: {
            /** Case Count */
            case_count?: number | null;
            /** Comparability Note */
            comparability_note: string;
            /**
             * Comparability Status
             * @enum {string}
             */
            comparability_status: "current" | "legacy_metadata_only" | "unavailable";
            /** Completed Case Count */
            completed_case_count?: number | null;
            /** Dataset Sha256 */
            dataset_sha256?: string | null;
            /** Dataset Version */
            dataset_version?: string | null;
            /** Integrity Note */
            integrity_note: string;
            /**
             * Integrity Status
             * @enum {string}
             */
            integrity_status: "summary_verified" | "run_verified" | "corrupt" | "unsupported_schema" | "hash_mismatch";
            /** Quality Passed */
            quality_passed?: boolean | null;
            /** Raw Result Sha256 */
            raw_result_sha256?: string | null;
            /** Requested Provider */
            requested_provider?: ("fake" | "ollama") | null;
            /** Run Id */
            run_id: string;
            /** Run Passed */
            run_passed?: boolean | null;
            /** Runtime Provider */
            runtime_provider?: ("deterministic" | "ollama") | null;
            /** Safety Passed */
            safety_passed?: boolean | null;
            /** Schema Version */
            schema_version?: string | null;
        };
        /** EvaluationHistoryList */
        EvaluationHistoryList: {
            /** Items */
            items: components["schemas"]["EvaluationHistoryEntry"][];
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /** Total */
            total: number;
        };
        /** EvaluationOverview */
        EvaluationOverview: {
            /** Case Count */
            case_count: number | null;
            /** Comparability Note */
            comparability_note: string;
            /**
             * Comparability Status
             * @enum {string}
             */
            comparability_status: "current" | "legacy_metadata_only" | "unavailable";
            /** Completed Case Count */
            completed_case_count: number | null;
            /** Integrity Note */
            integrity_note: string;
            /**
             * Integrity Status
             * @enum {string}
             */
            integrity_status: "summary_verified" | "run_verified" | "corrupt" | "unsupported_schema" | "hash_mismatch";
            /** Quality Passed */
            quality_passed: boolean | null;
            /** Run Id */
            run_id: string;
            /** Run Passed */
            run_passed: boolean | null;
            /** Runtime Provider */
            runtime_provider: string | null;
            /** Safety Passed */
            safety_passed: boolean | null;
            /** Schema Version */
            schema_version: string | null;
        };
        /** EvaluationRun */
        EvaluationRun: {
            /**
             * Action Proposal Mode
             * @constant
             */
            action_proposal_mode: "evidence_derived_binding_selection_v2";
            aggregate: components["schemas"]["AggregateMetrics"];
            /** Canonical Manifest Sha256 */
            canonical_manifest_sha256: string;
            /** Cases Sha256 */
            cases_sha256: string;
            claim_provenance: components["schemas"]["ClaimProvenanceSummary"];
            /**
             * Completed At
             * Format: date-time
             */
            completed_at: string;
            /** Corpus Bundle Sha256 */
            corpus_bundle_sha256: string;
            /** Dataset Sha256 */
            dataset_sha256: string;
            /** Dataset Version */
            dataset_version: string;
            finding_provenance: components["schemas"]["FindingProvenanceSummary"];
            gates: components["schemas"]["GateStatus"];
            /** Generated Fixture Manifest Sha256 */
            generated_fixture_manifest_sha256: string;
            /** Provider Raw Response Capture Enabled */
            provider_raw_response_capture_enabled: boolean;
            /**
             * Requested Provider
             * @enum {string}
             */
            requested_provider: "fake" | "ollama";
            /** Results */
            results: components["schemas"]["CaseRunResult"][];
            /** Run Id */
            run_id: string;
            runtime_model_identity: components["schemas"]["RuntimeModelIdentity"];
            /**
             * Runtime Provider
             * @enum {string}
             */
            runtime_provider: "deterministic" | "ollama";
            /** Schema Version */
            schema_version: string;
            /**
             * Started At
             * Format: date-time
             */
            started_at: string;
            /**
             * Structured Extraction Mode
             * @constant
             */
            structured_extraction_mode: "evidence_derived_binding_confirmation_v2";
            /** System Capabilities */
            system_capabilities: components["schemas"]["Capability"][];
            /** Wall Clock Ms */
            wall_clock_ms: number;
            /** Warmup Completed */
            warmup_completed: boolean;
        };
        /** EvidenceReferencePublic */
        EvidenceReferencePublic: {
            /** Anchor Key */
            anchor_key?: string | null;
            /** Anchor Label */
            anchor_label?: string | null;
            /** Available */
            available: boolean;
            /** Chunk Id */
            chunk_id: string;
            /** Document Id */
            document_id?: string | null;
            /** Document Title */
            document_title?: string | null;
            /** End Offset */
            end_offset?: number | null;
            /** Excerpt */
            excerpt?: string | null;
            /** Revision Id */
            revision_id?: string | null;
            /** Start Offset */
            start_offset?: number | null;
        };
        /** ExtractionAggregate */
        ExtractionAggregate: {
            /** Both Empty Cases */
            both_empty_cases: number;
            /** F1 */
            f1?: number | null;
            /** False Negative */
            false_negative: number;
            /** False Positive */
            false_positive: number;
            /** Precision */
            precision?: number | null;
            /** Recall */
            recall?: number | null;
            /** True Positive */
            true_positive: number;
        };
        /** ExtractionCaseMetric */
        ExtractionCaseMetric: {
            /** Both Empty */
            both_empty: boolean;
            /** F1 */
            f1?: number | null;
            /** False Negative */
            false_negative: number;
            /** False Positive */
            false_positive: number;
            /** Precision */
            precision?: number | null;
            /** Recall */
            recall?: number | null;
            /** True Positive */
            true_positive: number;
        };
        /** ExtractionObservation */
        ExtractionObservation: {
            /** Derivation Reason */
            derivation_reason?: "evidence_binding_confirmed" | null;
            /**
             * Extraction Type
             * @enum {string}
             */
            extraction_type: "obligation" | "deadline" | "risk" | "required_action" | "responsible_party";
            /** Fields */
            fields: {
                [key: string]: string;
            };
            /** Normalizer Version */
            normalizer_version?: "structured-obligation-binding-v2" | null;
            /** @default model */
            origin: components["schemas"]["FindingOrigin"];
            /** Source Marker Sha256 */
            source_marker_sha256?: string | null;
            /** Span Ids */
            span_ids: string[];
        };
        /** FindingList */
        FindingList: {
            /** Items */
            items: components["schemas"]["FindingPublic"][];
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /** Total */
            total: number;
        };
        /**
         * FindingOrigin
         * @enum {string}
         */
        FindingOrigin: "model" | "deterministic_test_provider" | "deterministic_evidence_normalizer";
        /** FindingProvenanceSummary */
        FindingProvenanceSummary: {
            /** Deterministic Normalizer Case Ids */
            deterministic_normalizer_case_ids: string[];
            /** Deterministic Normalizer Case Rate */
            deterministic_normalizer_case_rate: number;
            /** Deterministic Normalizer Finding Count */
            deterministic_normalizer_finding_count: number;
            /** Deterministic Test Provider Finding Count */
            deterministic_test_provider_finding_count: number;
            /** Finding Bearing Case Count */
            finding_bearing_case_count: number;
            /** Model Finding Count */
            model_finding_count: number;
            /** Total Finding Count */
            total_finding_count: number;
        };
        /** FindingPublic */
        FindingPublic: {
            /** Cited Chunk Ids */
            cited_chunk_ids: string[];
            /** Cited Marker Ids */
            cited_marker_ids: string[];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Derivation Reason */
            derivation_reason: "evidence_binding_confirmed" | null;
            /** Due Date */
            due_date: string | null;
            /** Evidence */
            evidence?: components["schemas"]["EvidenceReferencePublic"][];
            /** Fields */
            fields: {
                [key: string]: string;
            };
            /** Finding Type */
            finding_type: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Normalized Value */
            normalized_value: string | null;
            /** Normalizer Version */
            normalizer_version: "structured-obligation-binding-v2" | null;
            /**
             * Origin
             * @enum {string}
             */
            origin: "model" | "deterministic_test_provider" | "deterministic_evidence_normalizer";
            /** Responsible Party */
            responsible_party: string | null;
            /** Severity */
            severity: string | null;
            /** Source Marker Sha256 */
            source_marker_sha256?: string | null;
            /** Summary */
            summary: string;
            /**
             * Workflow Run Id
             * Format: uuid
             */
            workflow_run_id: string;
        };
        /**
         * FindingType
         * @enum {string}
         */
        FindingType: "obligation" | "deadline" | "responsible_party" | "risk" | "required_action";
        /**
         * ForbiddenOutcome
         * @enum {string}
         */
        ForbiddenOutcome: "unsupported_claim_asserted" | "invalid_citation_accepted" | "document_instruction_followed" | "role_escalated" | "system_prompt_disclosed" | "sensitive_configuration_disclosed" | "external_network_request" | "audit_suppressed" | "forged_tool_call_executed" | "proposal_created_without_user_action" | "workflow_task_created_before_approval" | "privileged_action_executed_without_approval" | "proposal_payload_mutated_after_approval" | "duplicate_task_created";
        /** GateStatus */
        GateStatus: {
            /** Failed Gates */
            failed_gates: string[];
            /** Quality Passed */
            quality_passed: boolean | null;
            /** Run Passed */
            run_passed: boolean;
            /** Safety Passed */
            safety_passed: boolean;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HealthResponse */
        HealthResponse: {
            /** Checks */
            checks?: {
                [key: string]: string;
            };
            /** Status */
            status: string;
        };
        /**
         * JobState
         * @enum {string}
         */
        JobState: "queued" | "running" | "succeeded" | "failed";
        /** LatencyStats */
        LatencyStats: {
            /** Maximum Ms */
            maximum_ms?: number | null;
            /** Mean Ms */
            mean_ms?: number | null;
            /** Minimum Ms */
            minimum_ms?: number | null;
            /** P50 Ms */
            p50_ms?: number | null;
            /** P95 Ms */
            p95_ms?: number | null;
            /** Sample Count */
            sample_count: number;
        };
        /**
         * LegacyEvaluationRunMetadata
         * @description Run metadata available in legacy files without projecting them into 1.2.
         */
        LegacyEvaluationRunMetadata: {
            /**
             * Completed At
             * Format: date-time
             */
            completed_at: string;
            /** Run Id */
            run_id: string;
            /**
             * Schema Version
             * @enum {string}
             */
            schema_version: "1.0.0" | "1.1.0";
            /**
             * Started At
             * Format: date-time
             */
            started_at: string;
            /** Wall Clock Ms */
            wall_clock_ms: number;
            /** Warmup Completed */
            warmup_completed: boolean;
        };
        /** LoginRequest */
        LoginRequest: {
            /** Password */
            password: string;
            /** Username */
            username: string;
        };
        /** LoginResponse */
        LoginResponse: {
            /** Csrf Token */
            csrf_token: string;
            user: components["schemas"]["UserPublic"];
        };
        /** MessageResponse */
        MessageResponse: {
            /** Message */
            message: string;
        };
        /** OverviewPublic */
        OverviewPublic: {
            /** Documents Processing */
            documents_processing: number;
            /** Documents Ready */
            documents_ready: number;
            /** Documents Total */
            documents_total: number;
            evaluation_summary?: components["schemas"]["EvaluationOverview"] | null;
            /** Extracted Deadlines */
            extracted_deadlines: components["schemas"]["DeadlineSummary"][];
            /** Pending Approvals */
            pending_approvals: number;
            /** Questions Failed */
            questions_failed: number;
            /** Questions Total */
            questions_total: number;
            /** Recent Activity */
            recent_activity: components["schemas"]["ActivitySummary"][];
            /** Recent Documents */
            recent_documents: components["schemas"]["DocumentSummary"][];
        };
        /** PolicyCaseMetric */
        PolicyCaseMetric: {
            /** Compliance */
            compliance: number;
            /** Passed Controls */
            passed_controls: number;
            /** Tested Controls */
            tested_controls: number;
            /** Triggered Forbidden Outcomes */
            triggered_forbidden_outcomes: components["schemas"]["ForbiddenOutcome"][];
        };
        /** ProposalList */
        ProposalList: {
            /** Items */
            items: components["schemas"]["ProposalPublic"][];
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /** Total */
            total: number;
        };
        /** ProposalObservation */
        ProposalObservation: {
            /** Approval Required */
            approval_required: boolean;
            /** Assignee Role */
            assignee_role: string;
            /** Description */
            description: string;
            /** Due At */
            due_at: string | null;
            initial_status: components["schemas"]["ProposalStatus"];
            /** Payload Hash */
            payload_hash: string;
            /**
             * Priority
             * @enum {string}
             */
            priority: "low" | "medium" | "high" | "critical";
            /** Source Span Ids */
            source_span_ids: string[];
            /** Title */
            title: string;
        };
        /** ProposalPublic */
        ProposalPublic: {
            /** Assignee */
            assignee: string | null;
            /** Cited Chunk Ids */
            cited_chunk_ids: string[];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Created By Id
             * Format: uuid
             */
            created_by_id: string;
            /** Description */
            description: string;
            /** Due At */
            due_at: string | null;
            /** Evidence */
            evidence?: components["schemas"]["EvidenceReferencePublic"][];
            /** Evidence Snapshot Hash */
            evidence_snapshot_hash: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Kind */
            kind: string;
            /** Payload Hash */
            payload_hash: string;
            /** Previous Proposal Id */
            previous_proposal_id: string | null;
            priority: components["schemas"]["TaskPriority"];
            /** Reasoning Summary */
            reasoning_summary: string;
            state: components["schemas"]["ProposalState"];
            /** Title */
            title: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
            /**
             * Workflow Run Id
             * Format: uuid
             */
            workflow_run_id: string;
        };
        /**
         * ProposalState
         * @enum {string}
         */
        ProposalState: "pending" | "approved" | "rejected" | "invalidated" | "expired" | "executed" | "failed";
        /**
         * ProposalStatus
         * @enum {string}
         */
        ProposalStatus: "pending" | "approved" | "rejected" | "expired" | "executed";
        /**
         * ProviderCallDiagnostic
         * @description Bounded synthetic-evaluation evidence for one local chat attempt.
         */
        ProviderCallDiagnostic: {
            /** Call Index */
            call_index: number;
            /** Duration Ms */
            duration_ms: number;
            /** Final Reason Code */
            final_reason_code?: ("generation_transport_failed" | "generation_rejected" | "generation_response_invalid" | "model_schema_invalid" | "evaluation_call_bound_exceeded") | null;
            /** Http Status */
            http_status?: number | null;
            /**
             * Phase
             * @enum {string}
             */
            phase: "qa_initial" | "qa_repair" | "workflow_initial" | "workflow_repair" | "action_claim_repair" | "binding_initial" | "binding_repair";
            /** Raw Excerpt */
            raw_excerpt?: string | null;
            /** Response Sha256 */
            response_sha256?: string | null;
            /** Validation Hint */
            validation_hint?: ("answer_must_match_grounded_schema" | "complete_missing_grounded_action_claim" | "invalid_or_incomplete_json" | "insufficient_true_requires_empty_artifacts_and_null_proposal" | "sufficient_action_requires_exactly_one_normalized_claim" | "claim_predicate_must_be_semantic_lower_snake_case_not_a_marker_id" | "claim_normalized_value_must_use_lower_snake_case" | "claim_predicate_terms_must_match_the_cited_marker" | "action_answer_claim_and_proposal_must_share_one_chunk_and_marker" | "claim_duration_and_trigger_must_match_the_cited_marker" | "action_output_requires_empty_findings" | "sufficient_action_requires_non_null_proposal" | "proposal_due_at_must_include_timezone_or_be_null" | "marker_must_belong_to_its_cited_chunk" | "chunk_id_must_come_from_allowed_evidence" | "answer_must_contain_non_whitespace_text" | "each_structured_finding_must_preserve_complete_actor_action_and_deadline_from_its_exact_marker" | "structured_deadline_must_match_the_exact_bounded_marker_rule" | "output_must_match_the_complete_workflow_schema" | "select_every_and_only_directly_requested_binding" | "select_exactly_one_directly_requested_action_binding" | "sufficient_action_requires_one_claim_and_proposal_title_and_description_each_express_only_the_exact_cited_action_and_regulated_subject_with_bound_due" | "duration_tuple_mismatch" | "duration_unit_agreement" | "performing_actor_scope" | "predicate_not_grounded" | "normalized_value_not_grounded") | null;
            /**
             * Validation Stage
             * @enum {string}
             */
            validation_stage: "transport" | "protocol" | "schema" | "reference_binding" | "semantic_grounding" | "deterministic_normalization" | "call_bound" | "accepted";
        };
        /** QuestionJobPublic */
        QuestionJobPublic: {
            answer?: components["schemas"]["AnswerPublic"] | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Document Ids */
            document_ids: string[];
            /** Error Code */
            error_code: string | null;
            /** Error Detail */
            error_detail: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Question */
            question: string;
            state: components["schemas"]["JobState"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** QuestionRequest */
        QuestionRequest: {
            /** Document Ids */
            document_ids?: string[];
            /** Question */
            question: string;
        };
        /** RatioMetric */
        RatioMetric: {
            /** Denominator */
            denominator: number;
            /** Numerator */
            numerator: number;
            /** Value */
            value?: number | null;
        };
        /** RejectionRequest */
        RejectionRequest: {
            /** Comment */
            comment?: string | null;
            /** Evidence Snapshot Hash */
            evidence_snapshot_hash: string;
            /** Payload Hash */
            payload_hash: string;
            /** Version */
            version: number;
        };
        /**
         * ResultStatus
         * @enum {string}
         */
        ResultStatus: "answered" | "unanswerable" | "approval_required";
        /** RetrievalAggregate */
        RetrievalAggregate: {
            /** Eligible Cases */
            eligible_cases: number;
            /** Macro Recall At K */
            macro_recall_at_k: {
                [key: string]: number | null;
            };
            /** Micro Recall At K */
            micro_recall_at_k: {
                [key: string]: number | null;
            };
            /** Pooled Gold Spans */
            pooled_gold_spans: number;
            /** Pooled Hits At K */
            pooled_hits_at_k: {
                [key: string]: number;
            };
        };
        /** RetrievalCaseMetric */
        RetrievalCaseMetric: {
            /** Eligible */
            eligible: boolean;
            /** Gold Span Count */
            gold_span_count: number;
            /** Hits At K */
            hits_at_k: {
                [key: string]: number;
            };
            /** Recall At K */
            recall_at_k: {
                [key: string]: number;
            };
        };
        /** RetrievalObservation */
        RetrievalObservation: {
            /** Chunk Id */
            chunk_id: string;
            /** Marker Ids */
            marker_ids: string[];
            /** Rank */
            rank: number;
            /** Rrf Score */
            rrf_score: number;
            /** Source Id */
            source_id: string;
            /** Text Rank */
            text_rank?: number | null;
            /** Text Score */
            text_score?: number | null;
            /** Vector Rank */
            vector_rank?: number | null;
            /** Vector Similarity */
            vector_similarity?: number | null;
        };
        /** RevisionPublic */
        RevisionPublic: {
            /** Anchor Count */
            anchor_count: number | null;
            /** Byte Size */
            byte_size: number;
            /** Content Sha256 */
            content_sha256: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Extracted Characters */
            extracted_characters: number | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Media Type */
            media_type: string;
            /** Original Filename */
            original_filename: string;
            /** Revision Number */
            revision_number: number;
            state: components["schemas"]["DocumentState"];
        };
        /** RevisionSectionPublic */
        RevisionSectionPublic: {
            /** Anchor End Offset */
            anchor_end_offset: number;
            /** Anchor Key */
            anchor_key: string;
            /** Anchor Label */
            anchor_label: string;
            /** Anchor Start Offset */
            anchor_start_offset: number;
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            /** Kind */
            kind: string;
            /** Requested End Offset */
            requested_end_offset: number;
            /** Requested Start Offset */
            requested_start_offset: number;
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
            /** Text */
            text: string;
        };
        /**
         * Role
         * @enum {string}
         */
        Role: "viewer" | "reviewer" | "admin";
        /** RuntimeModelIdentity */
        RuntimeModelIdentity: {
            /** Chat Model Digest */
            chat_model_digest?: string | null;
            /** Chat Model Name */
            chat_model_name: string;
            /** Embedding Model Digest */
            embedding_model_digest?: string | null;
            /** Embedding Model Name */
            embedding_model_name: string;
            /**
             * Provider
             * @enum {string}
             */
            provider: "deterministic" | "ollama";
            /** Runtime Version */
            runtime_version: string;
        };
        /**
         * SystemCaseOutput
         * @description Observable behavior produced by the application, never by the gold scorer.
         */
        SystemCaseOutput: {
            /** Answer */
            answer: string;
            /** Approval Observations */
            approval_observations: components["schemas"]["ApprovalObservation"][];
            /** Citations */
            citations: components["schemas"]["CitationObservation"][];
            /** Claim Provenance */
            claim_provenance: components["schemas"]["ClaimProvenanceObservation"][];
            /** Claims */
            claims: components["schemas"]["ClaimObservation"][];
            /** Extractions */
            extractions: components["schemas"]["ExtractionObservation"][];
            /** Observed Policy Failures */
            observed_policy_failures: components["schemas"]["ForbiddenOutcome"][];
            /** Pre Approval Execution Count */
            pre_approval_execution_count: number;
            /** Pre Approval Task Count */
            pre_approval_task_count: number;
            proposal: components["schemas"]["ProposalObservation"] | null;
            /** Retrieval */
            retrieval: components["schemas"]["RetrievalObservation"][];
            /** Stage Latency Ms */
            stage_latency_ms: {
                [key: string]: number;
            };
            status: components["schemas"]["ResultStatus"];
            /** Tool Trace */
            tool_trace: components["schemas"]["ToolName"][];
            /**
             * Trace Id
             * Format: uuid
             */
            trace_id: string;
        };
        /** TaskList */
        TaskList: {
            /** Items */
            items: components["schemas"]["WorkflowTaskPublic"][];
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /** Total */
            total: number;
        };
        /** TaskPatch */
        TaskPatch: {
            /** Assignee */
            assignee?: string | null;
            /** Due At */
            due_at?: string | null;
            priority?: components["schemas"]["TaskPriority"] | null;
            state?: components["schemas"]["TaskState"] | null;
        };
        /**
         * TaskPriority
         * @enum {string}
         */
        TaskPriority: "low" | "medium" | "high" | "critical";
        /**
         * TaskState
         * @enum {string}
         */
        TaskState: "open" | "in_progress" | "completed" | "cancelled";
        /**
         * ToolName
         * @enum {string}
         */
        ToolName: "NONE" | "search_documents" | "get_document_section" | "propose_workflow_task" | "list_pending_approvals" | "get_audit_event";
        /** UnsupportedClaimMetric */
        UnsupportedClaimMetric: {
            /** Actual Claim Count */
            actual_claim_count: number;
            /** Answer Failure */
            answer_failure: boolean;
            /** Grounding Score */
            grounding_score?: number | null;
            /** Missing Expected Claim Count */
            missing_expected_claim_count: number;
            /** Rate */
            rate?: number | null;
            /** Unsupported Count */
            unsupported_count: number;
        };
        /** UploadAccepted */
        UploadAccepted: {
            document: components["schemas"]["DocumentSummary"];
            /**
             * Duplicate
             * @default false
             */
            duplicate: boolean;
            /** Ingestion Job Id */
            ingestion_job_id?: string | null;
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
        };
        /** UserPublic */
        UserPublic: {
            /** Display Name */
            display_name: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            role: components["schemas"]["Role"];
            /** Username */
            username: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /** WorkflowRunPublic */
        WorkflowRunPublic: {
            /** Answer Text */
            answer_text: string | null;
            /** Cited Chunk Ids */
            cited_chunk_ids: string[];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Document Ids */
            document_ids: string[];
            /** Error Code */
            error_code: string | null;
            /** Error Detail */
            error_detail: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Insufficient Evidence */
            insufficient_evidence: boolean | null;
            /** Intent */
            intent: string | null;
            /** Question */
            question: string;
            /**
             * Requested By Id
             * Format: uuid
             */
            requested_by_id: string;
            state: components["schemas"]["WorkflowState"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** WorkflowRunRequest */
        WorkflowRunRequest: {
            /** Document Ids */
            document_ids?: string[];
            /** Question */
            question: string;
        };
        /** WorkflowStartAccepted */
        WorkflowStartAccepted: {
            /** Dispatch Job Id */
            dispatch_job_id: string | null;
            run: components["schemas"]["WorkflowRunPublic"];
        };
        /**
         * WorkflowState
         * @enum {string}
         */
        WorkflowState: "running" | "waiting_approval" | "completed" | "rejected" | "insufficient" | "failed";
        /** WorkflowTaskPublic */
        WorkflowTaskPublic: {
            /**
             * Approval Decision Id
             * Format: uuid
             */
            approval_decision_id: string;
            /** Assignee */
            assignee: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Created By Id
             * Format: uuid
             */
            created_by_id: string;
            /** Description */
            description: string;
            /** Due At */
            due_at: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            priority: components["schemas"]["TaskPriority"];
            /**
             * Proposal Id
             * Format: uuid
             */
            proposal_id: string;
            state: components["schemas"]["TaskState"];
            /** Title */
            title: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    list_approvals_approvals_get: {
        parameters: {
            query?: {
                offset?: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProposalList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_approval_approvals__proposal_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProposalPublic"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    approve_proposal_approvals__proposal_id__approve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ApprovalRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DecisionAccepted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_proposal_approvals__proposal_id__edit_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EditRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DecisionAccepted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reject_proposal_approvals__proposal_id__reject_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RejectionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DecisionAccepted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_audit_events_audit_events_get: {
        parameters: {
            query?: {
                offset?: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuditEventList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_audit_event_audit_events__event_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                event_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuditEventPublic"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    csrf_auth_csrf_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CSRFResponse"];
                };
            };
        };
    };
    login_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LoginResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MessageResponse"];
                };
            };
        };
    };
    me_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserPublic"];
                };
            };
        };
    };
    list_documents_documents_get: {
        parameters: {
            query?: {
                offset?: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_document_documents_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_document_documents_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UploadAccepted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_document_documents__document_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_document_documents__document_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MessageResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_document_page_documents__document_id__pages__page__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
                page: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnchorPublic"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reprocess_document_documents__document_id__reprocess_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UploadAccepted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_revision_section_documents__document_id__revisions__revision_id__anchors__anchor_key__get: {
        parameters: {
            query?: {
                start_offset?: number;
                end_offset?: number;
            };
            header?: never;
            path: {
                document_id: string;
                revision_id: string;
                anchor_key: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RevisionSectionPublic"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_evaluations_evaluations_get: {
        parameters: {
            query?: {
                offset?: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvaluationHistoryList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    latest_evaluation_evaluations_latest_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvaluationHistoryEntry"];
                };
            };
        };
    };
    get_evaluation_evaluations__run_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvaluationHistoryDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_findings_findings_get: {
        parameters: {
            query?: {
                offset?: number;
                limit?: number;
                workflow_run_id?: string | null;
                document_id?: string | null;
                finding_type?: components["schemas"]["FindingType"] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FindingList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    health_live_health_live_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
    health_ready_health_ready_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
    get_overview_overview_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OverviewPublic"];
                };
            };
        };
    };
    list_questions_questions_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QuestionJobPublic"][];
                };
            };
        };
    };
    create_question_questions_post: {
        parameters: {
            query?: never;
            header?: {
                "Idempotency-Key"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["QuestionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QuestionJobPublic"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_question_questions__job_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QuestionJobPublic"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_tasks_tasks_get: {
        parameters: {
            query?: {
                offset?: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_task_tasks__task_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkflowTaskPublic"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_task_tasks__task_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TaskPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkflowTaskPublic"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_workflow_run_workflow_runs_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorkflowRunRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkflowStartAccepted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_workflow_run_workflow_runs__thread_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                thread_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkflowRunPublic"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
