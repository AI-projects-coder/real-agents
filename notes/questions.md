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



1. Why did Cloud Build use the default compute service account, and why is relying on it a security risk?
2. What's the minimum set of permissions a build service account needs, and why grant artifactregistry.writer on the repo instead of the project?

module 2:

📝 Module 2 follow-up questions (2A + 2B)
Containers and Cloud Run

1. What are the 5 rules of Cloud Run's container contract, and what breaks if you ignore each one?
2. Why is the Dockerfile split into "dependencies first, code second"? What happens to build time if you reverse it?
Why run as a non-root user, and why exec in the CMD?
3. Concurrency = 80 and max-instances = 2. What's the maximum number of simultaneous requests? What happens to request 161?
Cold start: what causes it, how does min-instances=1 fix it, and what does that cost?
4. Why does the GCS client get created in lifespan and not inside each request handler?
5. Why are the endpoints plain def instead of async def here? When would async def be wrong?
6. Your container crashed locally without credentials but works on Cloud Run with no key file. Explain why.

Secrets and auth

1. Why must secret values never go into Terraform, and how did we avoid that?
You rotated the API key and the new key didn't work. Why, and how do you fix it in production without downtime?
2. Cloud Run IAM auth (--no-allow-unauthenticated) vs app-level API key: when do you use each?
3. Why does api_key have no default value in Settings? What is "fail fast"?

Build and CI/CD

1. docker buildx vs gcloud builds submit: what's the same and what's different?
2. Why did Cloud Build fall back to the default compute service account, and why is that risky?
3. Why does the build SA need iam.serviceAccountUser on shoppilot-dev? What attack does scoping it to one SA prevent?
Why tag images with the commit SHA instead of :latest?
4. Why do unit tests mock GCS instead of calling the real bucket?
5. What does --no-traffic plus --tag give you, and why smoke test before shifting traffic?
6. Canary vs blue/green vs all-at-once: when would you choose each?
7. Rollback took seconds. Why? And what's the "pinned revision" gotcha afterwards?

Debugging lessons from this module

1. localhost:8080 returned Streamlit HTML. What was the root cause, and which two commands find it fast?
2. Docker failed with input/output error. What was the real cause, and why do teams avoid building release images on laptops?


Module 3:


