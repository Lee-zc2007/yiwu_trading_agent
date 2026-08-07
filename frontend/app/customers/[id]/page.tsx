import { CustomerDetailPage } from '@/components/pages/customer-detail-page'
export default async function Page({params}:{params:Promise<{id:string}>}){const {id}=await params;return <CustomerDetailPage id={Number(id)}/>}
