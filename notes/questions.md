module:0
1	What's the difference between gcloud auth login and gcloud auth application-default login? Which one does your Python code use? (You hit a real bug with this. Explain what went wrong.)
1. Why is downloading a service-account JSON key dangerous, and what do we do instead?
2. A budget alert fires at 100%. Does GCP stop your resources? What would stop them on a free trial?
3. You call Vertex AI and get PERMISSION_DENIED: API not enabled. What happened, and what's the fix?
4. Why give each service (API, worker, agent) its own service account instead of one shared account?
5. Bonus (from your debugging): Your budget command failed with INVALID_ARGUMENT. Name two reasons it could happen, and explain why export variables "disappear."

module:1

📝 Module 1 follow-up questions (note these down for the final discussion)

Cloud Storage

1. GCS has "no real folders." What does that mean, and what's the practical consequence of "renaming a folder" with 10,000 files?
2. Why enforce uniform bucket-level access and public access prevention on every bucket?
3. Your signed URL returned AccessDenied until you granted objectViewer to the service account. Explain exactly why.
4. Give two real product features you'd build with signed URLs. Why not just make the bucket public?
5. Why did we grant objectViewer on the bucket instead of on the whole project?
Versioning is on. Someone deletes refund-policy.md. Is it gone? How do you recover it, and what keeps storage costs under control?
6. Why is it important to keep the bucket in the same region as the compute that reads it?

Terraform

1. Resource vs data source: when do you use each?
2. What is Terraform state, why store it remotely, and why must that bucket be locked down?
3. Why can't the state bucket be created by the same Terraform code that uses it?
In a plan, what's the difference between ~ and -/+? Which one should make you stop and think?
4. What is drift? How does Terraform detect and fix it? Is "fixing" drift always the right move?
5. What does prevent_destroy protect against, and what does it not protect against? (Hint: what if someone deletes the bucket in the console?)
Why commit .terraform.lock.hcl but never .tfstate?
6. (Scenario) Two engineers run terraform apply at the same time. What happens with GCS remote state, and why?
7. Terraform manages infrastructure, not data. Who tracks changes to files inside a bucket, and how?
8. Admin Activity vs Data Access audit logs: which is always on, and which costs money?
9. Why should only the CI pipeline run terraform apply on production?
10. Locking protects the state, not resources. What exactly goes wrong without it?




module 3:

Why did Cloud Build use the default compute service account, and why is relying on it a security risk?
What's the minimum set of permissions a build service account needs, and why grant artifactregistry.writer on the repo instead of the project?

