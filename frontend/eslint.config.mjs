import { defineConfig, globalIgnores } from 'eslint/config'
import nextCoreWebVitals from 'eslint-config-next/core-web-vitals'
import nextTs from 'eslint-config-next/typescript'

export default defineConfig([...nextCoreWebVitals, ...nextTs, globalIgnores(['.next/**', 'out/**', 'next-env.d.ts'])])
