import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

i18n.use(initReactI18next).init({
  resources: {
    zh: { translation: { buyer: '采购商视角', merchant: '商户视角', demo: 'Mock 演示模式', start: '开始路演' } },
    en: { translation: { buyer: 'Buyer View', merchant: 'Merchant View', demo: 'Mock Demo Mode', start: 'Start Pitch' } },
  },
  lng: 'zh',
  fallbackLng: 'zh',
  interpolation: { escapeValue: false },
})

export default i18n

