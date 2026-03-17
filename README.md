# Instagram Automation Tools

AI-powered Instagram lead generation, qualification, and outreach pipeline.

---

## Prerequisites

| Tool        | Version | Install                               |
| ----------- | ------- | ------------------------------------- |
| **Python**  | ≥ 3.11  | [python.org](https://www.python.org/) |
| **Node.js** | ≥ 18    | [nodejs.org](https://nodejs.org/)     |
| **pnpm**    | ≥ 8     | `npm install -g pnpm`                 |

You will also need accounts / API keys for:

- **Supabase** — database & auth ([supabase.com](https://supabase.com))
- **OpenAI** — GPT models ([platform.openai.com](https://platform.openai.com))
- **Anthropic** _(optional)_ — Claude models ([console.anthropic.com](https://console.anthropic.com))

---

## 1 · Clone the repo

```bash
git clone https://github.com/M0nGKol/Instagram-automation-tools.git
cd Instagram-automation-tools
```

---

## 2 · Backend setup

```bash
cd backend
```

### 2.1 Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # macOS / Linux
# venv\Scripts\activate    # Windows
```

### 2.2 Install dependencies

```bash
pip install -r requirements.txt
```

### 2.3 Install Playwright browsers

```bash
playwright install chrome
```

### 2.4 Configure environment variables

```bash
cp .env.example .env
```

Open `backend/.env` and fill in your keys:

```
URL=https://your-project.supabase.co
ANNON=your-supabase-anon-key
OPENAI_API_KEY=sk-proj-your-openai-api-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key
```

### 2.5 Start the API server

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at **http://localhost:8000**.
You can view the docs at **http://localhost:8000/docs**.

---

## 3 · Frontend setup

Open a **new terminal** and run:

```bash
cd frontend
```

### 3.1 Install dependencies

```bash
pnpm install
```

### 3.2 Start the dev server

```bash
pnpm dev
```

The app will be available at **http://localhost:3000**.

---

## 4 · Usage

1. Open **http://localhost:3000** in your browser.
2. **Sign up / Log in** with your account.
3. Go to **Accounts** → save your Instagram session (browser will open for you to log in).
4. Go to **Lead Generation** → enter your target interest and click **Start Smart Pipeline**.
5. The pipeline will:
   - 🧠 Generate a discovery plan with AI
   - 🔍 Scroll Instagram & scrape relevant accounts
   - ✅ Qualify each profile with AI scoring
   - ➕ Auto-follow qualified leads
6. View results in the **Results** table and **Saved Premium Leads** section.

---

## Project Structure

```
Instagram-automation-tools/
├── backend/
│   ├── api/              # FastAPI routers & shared models
│   ├── agents/           # AI brains (Discovery + Qualification)
│   ├── browser/          # Playwright automation (scrolling, scraping, search)
│   ├── pipeline/         # Lead generation pipeline orchestration
│   └── requirements.txt
├── frontend/
│   ├── app/              # Next.js pages
│   ├── components/       # UI components
│   ├── lib/              # API client & utilities
│   └── package.json
└── README.md
```

---

## Environment Variables

| Variable            | Required | Description                           |
| ------------------- | -------- | ------------------------------------- |
| `URL`               | ✅       | Supabase project URL                  |
| `ANNON`             | ✅       | Supabase anonymous key                |
| `OPENAI_API_KEY`    | ✅       | OpenAI API key (for GPT models)       |
| `ANTHROPIC_API_KEY` | Optional | Anthropic API key (for Claude models) |

---

## Troubleshooting

| Problem                    | Solution                                               |
| -------------------------- | ------------------------------------------------------ |
| `supabase_key is required` | Check that `URL` and `ANNON` are set in `backend/.env` |
| `playwright not found`     | Run `playwright install chrome`                        |
| Frontend can't reach API   | Ensure backend is running on port 8000                 |
| Instagram login redirect   | Re-save your Instagram session from the Accounts page  |

---

## License

Private — for authorized use only.
