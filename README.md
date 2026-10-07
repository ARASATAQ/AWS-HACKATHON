# NOVA-S Disaster Management System 🚨

![NOVA-S Command Center](https://img.shields.io/badge/Status-Production%20Ready-brightgreen?style=for-the-badge)
![AWS](https://img.shields.io/badge/Powered_by-AWS-orange?style=for-the-badge&logo=amazon-aws)
![Python](https://img.shields.io/badge/Backend-FastAPI-blue?style=for-the-badge&logo=fastapi)

NOVA-S is a next-generation, AI-driven Emergency Operations Command Center and Disaster Management System. It seamlessly integrates automated multi-hazard detection, a two-way Meta WhatsApp Cloud API emergency response bot, and an Amazon Bedrock Multimodal Vision triage engine.

## 🌟 Key Features

* **Advanced Command Center:** A modern, dark-themed, highly responsive admin dashboard built with FastAPI, Tailwind CSS, and Mapbox GL JS. Features real-time layer toggles for active hazards (Earthquakes, Floods, Tsunamis, Heatwaves, Wildfires).
* **AI Multimodal Triage (Amazon Bedrock):** Citizens can send photos of disasters via WhatsApp. Claude 3 Haiku analyzes the images to estimate water depth, structural damage, and thermal collapse, outputting a strict JSON severity assessment to prioritize rescue efforts.
* **Automated Hazard Telemetry:** 
  * **NASA FIRMS:** Live satellite wildfire tracking (VIIRS SNPP).
  * **Open-Meteo:** Real-time cloudburst (mm/h) and extreme heat (°C) monitoring.
  * **GDACS:** Live earthquake, tsunami, and cyclone alert feeds.
* **Live Dispatch Feeds:** Real-time visual tracking of Fire, Police, and Medical rescue units directly on the map, complete with Commander assignments.
* **WhatsApp Emergency Bot:** Two-way communication for SOS signals, interactive buttons, and automated safe-route generation.
* **AWS Native Architecture:**
  * **DynamoDB:** Persistent state for citizens, incidents, and hospital routing.
  * **S3:** Secure storage for evidence and disaster photography.
  * **SNS:** Outbound emergency SMS/Email broadcast manifests to hospitals.

## 🛠️ Tech Stack

* **Backend:** Python 3.11+, FastAPI, Uvicorn
* **Frontend:** HTML5, Tailwind CSS, Mapbox GL JS, FontAwesome
* **AI/ML:** Amazon Bedrock (`anthropic.claude-3-haiku-20240307-v1:0`), Scikit-learn Random Forests
* **Cloud Infrastructure:** AWS Boto3 (DynamoDB, S3, SNS)
* **Messaging:** Meta WhatsApp Cloud API (Graph API)

## 🚀 Getting Started

### Prerequisites
1. Python 3.11+
2. AWS Credentials (IAM User) configured with permissions for Bedrock, DynamoDB, S3, and SNS.
3. Meta Developer Account with WhatsApp Cloud API tokens.

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/ARASATAQ/AWS-HACKATHON.git
   cd AWS-HACKATHON/disaster_system
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure Environment Variables:
   Copy `.env.example` to `.env` and fill in your AWS Keys, Meta Tokens, and Mapbox Key.

### Running the Application
Start the FastAPI server:
```bash
python -m uvicorn main:app --reload --port 8000
```
* The Command Center will be available at `http://localhost:8000/dashboard`
* The WhatsApp Webhook will be active at `http://localhost:8000/api/webhook`

## 🛡️ License
This project is licensed under the MIT License.