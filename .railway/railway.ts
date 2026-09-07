import { defineRailway, github, preserve, project, service } from 'railway/iac'

export default defineRailway((context) => {
  const api = service('api', {
    source: github('CraigR973/mcu-app', { branch: 'main' }),
    build: {
      builder: 'DOCKERFILE',
      dockerfilePath: 'Dockerfile',
    },
    deploy: {
      healthcheckPath: '/api/v1/health/ready',
      healthcheckTimeout: 300,
      restartPolicyType: 'ON_FAILURE',
      restartPolicyMaxRetries: 3,
    },
    env: {
      DATABASE_URL: preserve(),
      ENVIRONMENT: 'production',
      FRONTEND_ORIGIN: preserve(),
      JWT_ACCESS_SECRET: {
        value: context.randomString('jwt-access-secret', 32),
        isSealed: true,
      },
      JWT_REFRESH_SECRET: {
        value: context.randomString('jwt-refresh-secret', 32),
        isSealed: true,
      },
    },
  })

  return project('mcu-app', {
    environments: ['production'],
    resources: [api],
  })
})
