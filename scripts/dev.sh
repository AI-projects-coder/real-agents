# Dev helpers for ShopPilot. Load with:  source scripts/dev.sh

# zsh: stop "!" inside double quotes from triggering history expansion (the dquote> trap)
[ -n "$ZSH_VERSION" ] && setopt NO_BANG_HIST


set -a; source .env; set +a
gcloud config configurations activate real-agents >/dev/null 2>&1

export URL=$(gcloud run services describe shoppilot-api --region=us-central1 --format='value(status.url)')
export KEY=$(gcloud secrets versions access latest --secret=shoppilot-api-key)

# t "<subject>" "<body>"  -> create a ticket, wait for the worker, print the classification
t() {
  local id r
  id=$(curl -s -X POST $URL/tickets -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
    -d "{\"customer_id\":\"C-1\",\"subject\":\"$1\",\"body\":\"$2\"}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["ticket_id"])')
  echo "🎫 $id created, waiting for worker..."
  for i in $(seq 1 15); do
    r=$(curl -s $URL/tickets/$id -H "X-API-Key: $KEY")
    echo "$r" | grep -q '"classified"' && break
    sleep 2
  done
  echo "$r" | python3 -c '
import sys, json
d = json.load(sys.stdin)
for k in ["ticket_id","classifier","category","priority","sentiment","needs_human","summary","llm_ms","tokens_in","tokens_out"]:
    print(f"  {k:12} {d.get(k)}")'
  echo
}

echo "✅ loaded: URL, KEY and t()"
