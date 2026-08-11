export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'
export type Paginated<T> = { items: T[]; total: number; page: number; page_size: number; pages: number }
export type Customer = { id:number; merchant_id:number; name:string; company_name:string; country:string; region:string; registration_number:string; email:string; phone:string; industry:string; main_product_category:string; identity_verified:boolean; blacklist_status:boolean; watchlist_status:boolean; cooperation_start_date:string|null; notes:string; current_credit_score:number|null; credit_risk_level:string|null; transaction_count:number; created_at:string; updated_at:string }
export type CreditScore = { id:number; customer_id:number; total_score:number; performance_score:number; stability_score:number; dispute_score:number; identity_score:number; relationship_score:number; risk_level:string; confidence_level:string; rule_version:string; calculated_at:string; explanation:string[] }
export type Transaction = { id:number; customer_id:number; order_number:string; product_category:string; product_name:string; amount:number; currency:string; order_time:string; payment_method:string; deposit_ratio:number; final_payment_status:string; refund_status:string; dispute_status:string; overdue_days:number; cancelled:boolean; shipping_country:string; shipping_address:string; created_at:string; updated_at:string }
export type RuleResult = { triggered:boolean; rule_code:string; rule_name:string; risk_level:string; risk_score:number; reason:string; evidence:Record<string,unknown> }
export type RiskAnalysis = { customer_id:number; order_id:number|null; risk_event_id:number|null; credit_score:number; credit_confidence:string; overall_risk_score:number; risk_level:RiskLevel; statistical_anomaly_score:number; anomaly_score:number; triggered_rules:RuleResult[]; main_reasons:string[]; recommendations:string[]; model_version:string; model_status:string; rule_version:string; disclaimer:string; feature_snapshot:Record<string,number> }
export type RiskEvent = { id:number; customer_id:number; order_id:number|null; risk_type:string; risk_level:RiskLevel; risk_score:number; title:string; description:string; triggered_rules:RuleResult[]; evidence:Record<string,unknown>; status:string; assigned_to:string; resolution:string; created_at:string; updated_at:string; resolved_at:string|null }
export type Dashboard = { metrics:Record<string,number>; risk_trend:{date:string;alerts:number;high:number}[]; risk_distribution:{name:string;value:number}[]; high_risk_customers:{id:number;company_name:string;country:string;score:number;risk_level:string}[]; latest_alerts:{id:number;title:string;risk_level:RiskLevel;risk_score:number;status:string;created_at:string}[] }
export type AgentEvidence = { source_type:string; source_id:string; summary:string }
export type AgentToolCall = { tool:string; arguments:Record<string,unknown>; summary:string }
export type AgentToolResult = { tool:string; arguments:Record<string,unknown>; success:boolean; data:unknown; summary:string; error_code:string|null; error_message:string|null }
export type AgentCallChainStep = { step:number; node:string; status:string; detail:Record<string,unknown> }
export type AgentStateSnapshot = { node:string; message:string; customer_id:number|null; intent:string; tool_calls:{name:string;arguments:Record<string,unknown>;purpose:string}[]; tool_results:AgentToolResult[]; evidence:AgentEvidence[]; final_answer:string }
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
}
export type ConversationToolCall = { tool:string; arguments:Record<string,unknown>; success:boolean; summary:string; error_code:string|null }
export type ConversationMessage = { id:number|null; role:'user'|'assistant'|'system'|'tool'; content:string; created_at:string; tool_calls:ConversationToolCall[]; tools_used:string[]; evidence:AgentEvidence[] }
export type ConversationHistory = { conversation_id:string; merchant_id:number; user_id:string; title:string; customer_id:number|null; created_at:string; updated_at:string; messages:ConversationMessage[] }
export type ConversationSummary = { conversation_id:string; merchant_id:number; user_id:string; title:string; customer_id:number|null; message_count:number; created_at:string; updated_at:string }
