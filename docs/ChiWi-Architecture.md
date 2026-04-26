# **ChiWi: Technical Blueprint for Multi-Agent AI Personal Finance**

## **1\. Design Philosophy: "Zero-Effort & Proactive"**

* **Minimal Input**: Financial tracking should not feel like a second job. Use ambient data (notifications) and natural language (chat) to eliminate manual forms.  
* **Multi-Agent Coordination**: Specific tasks are delegated to specialized AI agents that "communicate" to reach a consensus on data classification and advice.  
* **Proactive Interaction**: The system doesn't wait for a query. It observes patterns and nudges the user based on anomalies, positive trends, or psychological triggers.

## **2\. Multi-Agent Ecosystem**

The system operates as a swarm of agents, each with a distinct system prompt and toolset:

1. **Ingestion Agent (The Collector)**:  
   * *Input*: Bank notifications via Webhooks (MacroDroid/Tasker).  
   * *Task*: Filter out noise (non-financial messages), extract raw amounts, currency, and merchant names.  
2. **Conversational Agent (The Interface)**:  
   * *Input*: Direct Telegram messages ("Spent 100k on coffee yesterday").  
   * *Task*: Resolve temporal references (yesterday, last Friday) and intent. It maintains the "persona" of ChiWi.  
3. **Context & Tagging Agent (The Classifier)**:  
   * *Input*: Raw data from Collector/Conversational agents.  
   * *Task*: Map merchants to categories and generate deep metadata/tags (e.g., morning, work-related, photography-hobby). It uses historical data to ensure consistency.  
4. **Behavioral Agent (The Psychologist)**:  
   * *Input*: Aggregated transaction streams and User Profile (DevOps, Film Photographer).  
   * *Task*: Analyze sentiment and habits. It identifies "Stress Buying" or "Progressive Saving." It is the one that sends "Nudges."  
5. **Reporting Agent (The Strategist)**:  
   * *Input*: Database records.  
   * *Task*: Generate periodic deep-dives, portfolio health checks, and long-term financial forecasting.

## **3\. Tech Stack Analysis**

| Component | Choice | Pros | Cons | Reason for Selection |
| :---- | :---- | :---- | :---- | :---- |
| **Backend** | **FastAPI (Python)** | High performance, native support for Pydantic (data validation) and AI libs (LangGraph). | Requires careful async management. | Best for AI-orchestration and easy to Dockerize. |
| **Database** | **MongoDB** | Schema-less (perfect for AI metadata), high write throughput. | More complex complex joins compared to SQL. | AI agents often generate unpredictable tags/metadata. Mongo handles this natively. |
| **AI Engine** | **Gemini 2.5 Flash/Pro** | Massive context window, native JSON mode, multi-modal capabilities. | API latency, cost (if used excessively). | Flash for speed (parsing), Pro for logic (behavioral analysis). |
| **Interface** | **Telegram Bot API** | Zero UI dev effort, built-in notifications, cross-platform. | Limited UI flexibility (solved by Mini Apps). | "Zero-effort" philosophy starts with the UI you already use. |
| **Cache/State** | **Redis** | Sub-millisecond latency for chat session management. | Extra component to maintain. | Essential for keeping track of multi-turn agent conversations. |

## **4\. Architecture & Flow**

### **High-Level Architecture**

graph TD  
    A\[Bank SMS / Telegram Chat\] \--\> B\[FastAPI Gateway\]  
    B \--\> C{Agent Orchestrator}  
    C \--\> D\[Parsing Agent\]  
    C \--\> E\[Context/Tagging Agent\]  
    D & E \--\> F\[(MongoDB)\]  
    F \--\> G\[Behavioral Agent\]  
    G \--\> H\[Proactive Nudges/Alerts\]  
    F \--\> I\[Reporting Agent\]  
    I \--\> J\[Telegram Mini App Dashboard\]

### **Mid-Level Transaction Flow**

1. **Event**: User pays 100k via bank app.  
2. **Webook**: MacroDroid captures notification \-\> Sends JSON to FastAPI.  
3. **Parsing**: Agent A extracts "100,000 VND" and "Highlands Coffee".  
4. **Enrichment**: Agent B recognizes "Highlands" \-\> Tags: Food & Beverage, Cafe, Morning Routine.  
5. **Verification**: Bot sends a silent "Saved" message to Telegram with an "Edit" button.  
6. **Observation**: Behavioral Agent notes this is the 5th coffee this week.  
7. **Nudge**: Next morning, Bot sends: "Hey Huy, maybe brew coffee at home today? You've spent 500k on Highlands this week \- that's half a roll of Kodak Portra\!"

## **5\. Granular Roadmap**

### **Phase 1: Foundation (The Data Pipe)**

* **1.1**: Setup Dockerized FastAPI \+ MongoDB \+ Redis.  
* **1.2**: Implement Telegram Bot base and webhook listener for Android notifications.  
* **1.3**: Deploy **Parsing Agent** (Basic Gemini 1.5 Flash prompt) to handle 80% of common bank formats.  
* *Metric*: 90% accuracy in amount/merchant extraction.

### **Phase 2: Intelligence (Context & Memory)**

* **2.1**: Implement **Context/Tagging Agent** with "Historical Memory" (retrieving previous tags from Mongo).  
* **2.2**: Build the Chat-to-Transaction logic (natural language processing).  
* **2.3**: Basic daily summary report via Telegram.  
* *Metric*: User correction rate \< 10%.

### **Phase 3: Proactivity (The Behavioral Engine)**

* **3.1**: Implement **Behavioral Agent** with user profiling (Nghề nghiệp, sở thích). ✅ Done  
* **3.2**: Create the "Nudge" engine — automated triggers (subscription reminders wired; spending_alert/budget_warning TODO). ✅ Partially done  
* **3.3**: ~~Build a Telegram Mini App for visual charts (React/Tailwind)~~ — **Deferred.** Android/dashboard app will be built in a separate repository.  
* *Metric*: User engagement with nudges (replies/actions).

## **6\. Security**

* **Data Masking**: PII (Personally Identifiable Information) like Account Numbers or Phone Numbers are stripped at the Gateway level before reaching Gemini.  
* **Encryption at Rest**: MongoDB collections are encrypted.  
* **Auth**: Telegram user\_id validation. Only your specific ID can trigger the API.  
* **Privacy**: Since it's self-hosted on your infrastructure, no third-party (except the AI provider) sees the aggregate data.

## **7\. Success Metrics**

* **Input Friction**: Number of manual clicks required per transaction (Target: \< 1).  
* **Classification Accuracy**: AI-assigned tags vs. manual corrections (Target: \> 95%).  
* **Financial Awareness**: Number of times the user changes a spending decision based on a "Nudge".  
* **System Reliability**: Gateway uptime and API latency (Target: \< 2s response for chat).