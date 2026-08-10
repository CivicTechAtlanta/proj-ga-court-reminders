## Things to be aware of
- If you delete and recreate the GithubActionStack, make sure to update AWS_GITHUBACTIONROLE_ARN secret for the repo. It will be in Settings
- The thumbprint value in the `OIDCProvider` could potentially change. If the aws config step fails, this could be something to check.