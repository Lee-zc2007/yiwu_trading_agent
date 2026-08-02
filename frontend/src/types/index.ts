export type JsonMap = Record<string, any>

export interface Product {
  id: number
  name: string
  category: string
  sku: string
  description: string
  price: number
  cost: number
  moq: number
  stock: number
  lead_days: number
  target_markets: string
  tags: string
  multilingual_points: string
  model_config: string
  popularity: number
}

export interface Customer {
  id: number
  company: string
  contact: string
  country: string
  email: string
  registered_years: number
  historical_orders: number
  historical_amount: number
  source: string
  intent_level: string
  risk_level: string
  credit_score: number
  last_contact: string
  tags: string
}

export interface Inquiry {
  id: number
  inquiry_no: string
  customer: string
  country: string
  product: string
  quantity: number
  target_price: number
  payment_method: string
  destination: string
  expected_delivery: string
  status: string
  intent_score: number
  risk_score: number
  ai_summary: string
  recommended_action: string
}

export interface Order {
  id: number
  order_no: string
  customer: string
  product: string
  quantity: number
  amount: number
  profit: number
  payment_status: string
  production_status: string
  logistics_status: string
  risk_status: string
  expected_delivery: string
  progress: number
}

