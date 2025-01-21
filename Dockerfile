steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-t', 'gcr.io/$PROJECT_ID/trading-bot', '.']

- name: 'gcr.io/cloud-builders/docker'
  args: ['push', 'gcr.io/$PROJECT_ID/trading-bot']

- name: 'gcr.io/cloud-builders/gcloud'
  args:
  - 'run'
  - 'deploy'
  - 'trading-bot'
  - '--image'
  - 'gcr.io/$PROJECT_ID/trading-bot'
  - '--platform'
  - 'managed'
  - '--region'
  - 'europe-west9'
  - '--memory'
  - '512Mi'
  - '--cpu'
  - '1'
  - '--min-instances'
  - '1'
  - '--timeout'
  - '3600s'
  - '--allow-unauthenticated'
  - '--set-env-vars'
  - 'XTB_USER_ID=17373384,XTB_PASSWORD=Java090214&Clement06032005*'
