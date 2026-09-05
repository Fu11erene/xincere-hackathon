import { defineConfig } from 'orval'

export default defineConfig({
  api: {
    input: 'http://localhost:8000/openapi.json',
    output: {
      mode: 'single',
      target: 'src/api/generated/endpoints.ts',
      schemas: 'src/api/generated/model',
      client: 'react-query',
      httpClient: 'axios',
      override: {
        mutator: {
          path: 'src/api/mutator.ts',
          name: 'customInstance',
        },
      },
    },
  },
})
