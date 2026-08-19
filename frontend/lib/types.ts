export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'
export type Paginated<T> = { items: T[]; total: number; page: number; page_size: number; pages: number }
export type Customer = { id:number; merchant_id:number; name:string; company_name:string; country:string; region:string; registration_number:string; email:string; phone:string; industry:string; main_product_category:string; identity_verified:boolean; blacklist_status:boolean; watchlist_status:boolean; cooperation_start_date:string|null; notes:string; current_credit_score:number|null; credit_risk_level:string|null; transaction_count:number; created_at:string; updated_at:string }
export type CreditScore = { id:number; customer_id:number; total_score:number; performance_score:number; stability_score:number; dispute_score:number; identity_score:number; relationship_score:number; risk_level:string; confidence_level:string; rule_version:string; calculated_at:string; explanation:string[] }
export type Transaction = { id:number; customer_id:number; order_number:string; product_category:string; product_name:string; amount:number; currency:string; order_time:string; payment_method:string; deposit_ratio:number; final_payment_status:string; refund_status:string; dispute_status:string; overdue_days:number; cancelled:boolean; shipping_country:string; shipping_address:string; created_at:string; updated_at:string }
export type RuleResult = { triggered:boolean; rule_code:string; rule_name:string; risk_level:string; risk_score:number; severity?:string; risk_contribution?:number; reason:string; evidence:Record<string,unknown> }
export type RiskAnalysis = { customer_id:number; order_id:number|null; risk_event_id:number|null; credit_score:number; credit_confidence:string; overall_risk_score:number; risk_level:RiskLevel; statistical_anomaly_score:number; anomaly_score:number; triggered_rules:RuleResult[]; main_reasons:string[]; recommendations:string[]; model_version:string; model_status:string; rule_version:string; disclaimer:string; feature_snapshot:Record<string,number> }
export type RiskEvent = { id:number; customer_id:number; order_id:number|null; risk_type:string; risk_level:RiskLevel; risk_score:number; title:string; description:string; triggered_rules:RuleResult[]; evidence:Record<string,unknown>; status:string; assigned_to:string; resolution:string; created_at:string; updated_at:string; resolved_at:string|null }
export type Dashboard = { metrics:Record<string,number>; risk_trend:{date:string;alerts:number;high:number}[]; risk_distribution:{name:string;value:number}[]; high_risk_customers:{id:number;company_name:string;country:string;score:number;risk_level:string}[]; latest_alerts:{id:number;title:string;risk_level:RiskLevel;risk_score:number;status:string;created_at:string}[] }
export type AgentEvidence = { source_type:string; source_id:string; summary:string }
export type AgentToolCall = { tool:string; arguments:Record<string,unknown>; summary:string }
export type AgentToolResult = { tool:string; arguments:Record<string,unknown>; success:boolean; data:unknown; summary:string; error_code:string|null; error_message:string|null }
export type AgentCallChainStep = { step:number; node:string; status:string; detail:Record<string,unknown> }
export type TransactionContext = {
  amount?:number; currency?:string; deposit_ratio?:number; deposit_amount?:number; confirmed_payment_amount?:number
  credit_days?:number; final_payment_ratio?:number; final_payment_due_type?:string; contract_signed?:boolean
  identity_verified?:boolean; payer_matches_contract?:boolean; payment_account_changed?:boolean
  payment_account_verified?:boolean; planned_shipping_value?:number; planned_payment_before_shipping?:number
  partial_payment?:boolean; partial_shipment?:boolean; payment_terms_verified?:boolean
  mitigations?:Record<string,unknown>[]; evidence_items?:Record<string,unknown>[]; [key:string]:unknown
}
export type CustomerTrust = { customer_id:number|null; transaction_count:number; cooperation_days:number; total_amount:number; max_order_amount:number; on_time_payment_rate:number|null; payment_timing_assessed_count:number; overdue_count:number; average_overdue_days:number|null; refund_count:number; refund_rate:number|null; dispute_count:number; dispute_rate:number|null; rejection_count:number; identity_verified:boolean; trust_level:string; confidence_level:string; missing_fields:string[]; calculation_version:string; reason:string }
export type DecisionResult = {
  customer_trust:CustomerTrust
  transaction_risk:{risk_level:RiskLevel;risk_score:number;triggered_rules:RuleResult[];main_reasons:string[];rule_version:string}
  risk_exposure:{currency:string;order_amount:number;confirmed_payment_amount:number;current_exposure:number;projected_max_exposure:number;coverage_amount:number;coverage_ratio:number}
  evidence:{completeness:number;required:{evidence_type:string;weight:number;critical:boolean}[];verified:string[];missing:string[];critical_missing:string[]}
  mitigations:{currency:string;verified_mitigations:Record<string,unknown>[];unverified_mitigations:Record<string,unknown>[];coverage_amount:number;coverage_ratio:number}
  anomaly_signal:{anomaly_detected:boolean;anomaly_score:number;model_version:string;feature_deviations:Record<string,unknown>[];explanation:string;signal_role:string}
  credit_terms:{status:string;credit_recommended:boolean;recommended_credit_days:number;recommended_max_exposure:number;recommended_min_deposit_ratio:number;recommended_payment_milestones:string[];partial_payment_recommended:boolean;partial_shipment_recommended:boolean;required_evidence:string[];recommendations:string[];human_decision_required:boolean}
  decision_status:string;main_risks:string[];missing_information:string[];recommendations:string[];calculation_version:string;disclaimer:string
}
export type DecisionSimulation = { adjustments:Record<string,unknown>; before:DecisionResult; after:DecisionResult; comparison:{projected_exposure_change:number;deposit_ratio_before:number|null;deposit_ratio_after:number|null;credit_days_before:number|null;credit_days_after:number|null;decision_status_before:string;decision_status_after:string}; persisted:false }
export type AgentStateSnapshot = { node:string; message:string; customer_id:number|null; intent:string; tool_calls:{name:string;arguments:Record<string,unknown>;purpose:string}[]; tool_results:AgentToolResult[]; evidence:AgentEvidence[]; final_answer:string; transaction_id:number|null; context_version:number; transaction_context:TransactionContext; required_fields:string[]; missing_fields:string[]; information_completeness:number; next_best_question:string; decision_result:DecisionResult|null; comparison:DecisionSimulation['comparison']|null }
export type RelatedCustomer = { id:number; company_name:string; country:string }
export type AgentResponse = {
  answer:string
  tools_used:string[]
  evidence:AgentEvidence[]
  related_customer:RelatedCustomer|null
  related_orders:number[]
  risk_events:number[]
  mode:string
  intent:string
  conversation_id:string
  call_chain:AgentCallChainStep[]
  state_history:AgentStateSnapshot[]
  tools_called:AgentToolCall[]
  data_sources:string[]
  related_customer_ids:number[]
  related_order_ids:number[]
  related_risk_event_ids:number[]
  insufficient_data:boolean
  disclaimer:string
  transaction_id:number|null
  context_version:number
  transaction_context:TransactionContext
  required_fields:string[]
  missing_fields:string[]
  information_completeness:number
  next_best_question:string
  decision_result:DecisionResult|null
  comparison:DecisionSimulation['comparison']|null
}
export type ConversationToolCall = { tool:string; arguments:Record<string,unknown>; success:boolean; summary:string; error_code:string|null }
export type ConversationMessage = { id:number|null; role:'user'|'assistant'|'system'|'tool'; content:string; created_at:string; tool_calls:ConversationToolCall[]; tools_used:string[]; evidence:AgentEvidence[] }
export type ConversationHistory = { conversation_id:string; merchant_id:number; user_id:string; title:string; customer_id:number|null; created_at:string; updated_at:string; messages:ConversationMessage[] }
export type ConversationSummary = { conversation_id:string; merchant_id:number; user_id:string; title:string; customer_id:number|null; message_count:number; created_at:string; updated_at:string }
