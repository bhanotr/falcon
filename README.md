# Falcon University Admission Bot

An AI-powered admission pre-assessment system for Falcon University. Students complete an automated interview via a chat interface; admins can review applications, manage knowledge base documents, and view transcripts through a dashboard.

---

## Architecture

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 15 (App Router, React, Tailwind CSS) |
| Backend | FastAPI (Python) |
| Database | PostgreSQL 15 |
| LLM Gateway | LiteLLM (OpenAI-compatible proxy) |
| Embeddings | Ollama (local embedding model) |
| Reverse Proxy | Nginx |
| Deployment | AWS CDK + EC2 (`c7i-flex.large`) |

All services run as Docker containers on a single EC2 instance connected via a named bridge network (`falcon`).

---

## Live Instance

> **Public IP:** `18.118.121.228`

| Route | Purpose | Access |
|-------|---------|--------|
| `http://18.118.121.228/` | **Student Interview** — start the admission pre-assessment | Public |
| `http://18.118.121.228/login` | **Admin Login** — sign in to the admin dashboard | Protected |
| `http://18.118.121.228/admin/applicants` | **Admin Dashboard** — review applicants & transcripts | Requires login |
| `http://18.118.121.228/admin/knowledge-bases` | **Knowledge Base** — upload/manage PDF documents | Requires login |

### Admin Credentials
- **Username:** `admin`
- **Password:** `admin123`

---

## Local Development (Podman / Docker)

### Prerequisites
- Podman or Docker with Compose plugin
- Git
- An OpenAI API key

### 1. Clone the repository

```bash
git clone https://github.com/bhanotr/falcon.git
cd falcon
```

### 2. Create environment file

```bash
cat > .env << 'EOF'
OPENAI_API_KEY=sk-your-key-here
SECRET_KEY=your-secret-key
EOF
```

### 3. Start all services

```bash
docker compose up -d --build
```

### 4. Access locally

- Frontend: http://localhost
- Backend API: http://localhost/api/health

---

## AWS Deployment (CDK)

### Prerequisites
- AWS CLI configured with credentials
- Python 3.9+
- Node.js 20+ (for CDK CLI)
- AWS CDK bootstrapped in your target region

### 1. Bootstrap CDK (one-time per region)

```bash
cd cdk
npx cdk bootstrap aws://YOUR_ACCOUNT_ID/us-east-2
```

### 2. Deploy the stack

```bash
npx cdk deploy -c openai_key="sk-your-key-here"
```

> **Note:** Do **not** commit your OpenAI API key to git. Pass it via the `-c` CLI flag only.

### 3. Retrieve the instance IP

After deployment completes, CDK outputs the public IP:

```
FalconStack.InstancePublicIp = 18.118.121.228
```

### 4. Wait for bootstrap

The EC2 instance runs a user-data script that installs Docker, clones the repo, and starts containers. This takes **3–5 minutes** after the CloudFormation stack shows `CREATE_COMPLETE`.

### Tear down

```bash
npx cdk destroy --force
```

This terminates the EC2 instance, security group, IAM role, and all associated resources.

---

## Project Structure

```
.
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── main.py          # API routes & interview logic
│   │   ├── knowledge_base.py# Document ingestion & RAG
│   │   ├── database.py      # SQLAlchemy models & session
│   │   └── schemas.py       # Pydantic models
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                # Next.js 15 application
│   ├── src/
│   │   ├── app/             # App router pages
│   │   ├── components/      # Reusable UI components
│   │   └── lib/api.ts       # API client helper
│   ├── Dockerfile
│   └── package.json
├── llm-gateway/             # LiteLLM proxy configuration
├── ollama/                  # Ollama embedding service
├── nginx/
│   └── nginx.conf           # Reverse proxy config
├── docker-compose.yml       # Local / EC2 orchestration
├── cdk/                     # AWS CDK infrastructure
│   ├── app.py               # CDK app entry point
│   ├── falcon_stack/
│   │   └── falcon_stack.py  # EC2, SG, IAM, user-data
│   └── requirements.txt
└── README.md
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for LLM calls | *(required)* |
| `SECRET_KEY` | JWT / session secret | `supersecretkey` |
| `ADMIN_USERNAME` | Admin dashboard username | `admin` |
| `ADMIN_PASSWORD` | Admin dashboard password | `admin123` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://falcon:falconpass@db:5432/falcon_university` |
| `LLM_GATEWAY_URL` | LiteLLM proxy base URL | `http://llm-gateway:11434/v1` |
| `OLLAMA_URL` | Ollama embeddings base URL | `http://ollama-embedding:11435` |

---

## Tech Stack Details

- **Next.js 15** with `output: "standalone"` for production-optimized Docker builds
- **FastAPI** with SQLAlchemy 2.0 and Pydantic v2
- **PostgreSQL 15** (Alpine image) with health checks
- **LiteLLM** proxying OpenAI-compatible requests
- **Ollama** running a local embedding model (`embeddinggemma:300m`)
- **Nginx** routing `/api/*` to the backend and all other traffic to the frontend
- **AWS CDK (Python)** defining VPC, Security Group, IAM Role, and EC2 instance with user-data bootstrap

---

## License

MIT
