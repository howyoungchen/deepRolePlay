# DeepRolePlay: Deep Role-Playing System Based on Multi-Agent Architecture

English | [中文](README.md)

## Project Overview

DeepRolePlay is a groundbreaking multi-agent role-playing system that completely solves the character forgetting problem of traditional large language models through Agent collaboration mechanisms.

DeepRolePlay adopts a multi-agent division of labor architecture: **Memory Flashback Agent** + **Scenario Update Agent** + **Main Conversation Model**, enabling AI to bid farewell to character forgetting and achieve truly coherent role-playing.

## 🚀 Solving Core Pain Points of Role-Playing

<img src="pics/generate.png" alt="DeepRolePlay Demo" width="200">

### 😤 Have You Ever Encountered These Problems?
- 🤖 **AI Suddenly Forgets Character Settings**: A mage suddenly picks up a sword
- 📖 **Inconsistent Plot**: Important plots from yesterday are completely forgotten today
- 💸 **Huge Token Consumption**: Long conversation costs skyrocket, experience interrupted

### ✅ DeepRolePlay's Solutions
- 🧠 **Never Forget**: Agent automatically maintains character memory, settings permanently preserved
- 🔄 **Plot Coherence**: Intelligent scenario updates, logical clarity even after millions of conversation rounds
- 💰 **Cost Control**: Scenario compression technology, long conversation costs reduced by 80%
- 📚 **Intelligent Internet Access**: Integrated Wikipedia, automatic completion of character backgrounds and story settings
- 🗂️ **Structured Management**: JSON table system manages worldview, characters, items, etc., supports dynamic CRUD operations
- ⚡ **Plug and Play**: 5-minute integration, direct use with SillyTavern and other platforms
- 🚀 **Ultra-Fast Response**: Using Qwen3-235B intelligent agents, only 2 AI calls needed in Fast mode, just 10 seconds longer than normal responses

## 🎯 How to Use

### 💾 Quick Start - Ready-to-Use Version

1. **📦 Extract Software Package**
   - Download the released software package and extract it to a **non-Chinese path**
   - The extracted folder contains: `config.yaml` configuration file + `DeepRolePlay.exe` main program

2. **⚙️ Modify Configuration File**
   
   Edit the `config.yaml` file, **Qwen3-235B is strongly recommended for intelligent agents (only 2 AI calls needed in Fast mode, just 10 seconds longer response than normal)**:

   ```yaml
   # API Proxy Configuration - Forwarding Target
   proxy:
     target_url: "https://api.deepseek.com/v1"                      # Your forwarding API address, DeepSeek recommended
     timeout: 60                                                     # Recommended 60 seconds
   
   # Workflow Control Configuration
   langgraph:
     max_history_length: 7                                           # Number of historical messages passed to forwarding target LLM, controls context length and token consumption
     stream_workflow_to_frontend: false                              # DRP workflow push switch, by default does not push DRP content to frontend, set to true and import deeproleplay.json regex in SillyTavern if push is needed
   
   # Agent Configuration - Model used by Agent (Recommended Qwen3-235B)
   agent:
     model: "qwen/qwen3-235b-a22b-2507"                             # Recommended: qwen3-235b
     base_url: "https://openrouter.ai/api/v1"                        # OpenRouter API address
     api_key: "your-openrouter-api-key"                              # Fill in your OpenRouter API Key
     temperature: 0.7
     max_iterations: 25
   
   # Server Configuration
   server:
     host: "0.0.0.0"
     port: 6666                                                      # Remember this port number
   ```

3. **🚀 Start Program**
   - Double-click `DeepRolePlay.exe` to start
   - You can see the project running normally in the terminal
   - 🌟 This project will check if the port is occupied. If it is, it will automatically increment by 1. Therefore, the actual port needs to be checked from the terminal output.

4. **🔗 Configure Role-Playing Frontend**
   - In platforms like SillyTavern, OpenWebUI
   - Change `base_url` to: `http://localhost:6666/v1`
   - Keep API Key unchanged (will be automatically forwarded)
   - **Important**: Disable history record limits, must send full history to proxy! (Don't worry about token explosion, max_history_length will control it)

5. **🎭 Start Role-Playing**
   - Immediately enjoy forgetting-free role-playing experience!
   - **When changing characters**: Type "deeproleplay" and send to clear history cache and restart

### 🔧 Compatibility Description
- ✅ **Fully Compatible with OpenAI API Format**: All tools supporting OpenAI can be used directly
- ✅ **Support Mainstream Models**: Gemini, DeepSeek, Claude, local Ollama, etc.
- ✅ **Dual Configuration**: Agent and forwarding target can use different models, flexible cost optimization

## Agent Working Principle

Traditional single model problem: **Character Forgetting** → **Plot Breakdown** → **Experience Collapse**

DeepRolePlay's Agent Solution:
- 🔍 **Memory Flashback Agent**: Intelligently retrieves historical conversations and external knowledge
- 📝 **Scenario Update Agent**: Real-time maintenance of character state and plot coherence, supports tabular data management
- 🗂️ **Table Management System**: Structured storage of worldview, characters, items, etc., supports dynamic CRUD operations
- 🎭 **Main Conversation Model**: Generates character responses based on complete context

## Workflow

```
User Request -> HTTP Proxy Service
           |
           v
    Trigger Workflow Execution
           |
    +------+------+
    |             |
    v             v
Memory Flashback  Scenario Update
    Agent           Agent
    |             |
    |      Table Management
    |        (CRUD)
    |             |
    +------+------+
           |
           v
    Inject Updated Scenario
           |
           v
    Forward to Target LLM
           |
           v
    Return Enhanced Response
```

## Developer Guide

### Environment Requirements

- Python 3.12
- UV Virtual Environment Manager (Recommended)

### 1. Install Project

```bash
git clone https://github.com/yourusername/deepRolePlay.git
cd deepRolePlay
uv venv --python 3.12
uv pip install -r requirements.txt
```

### 2. Configure Service

Edit `config/config.yaml` file, **Qwen3-235B is recommended (fast response)**:

```yaml
# API Proxy Configuration - Forwarding Target
proxy:
  target_url: "https://api.deepseek.com/v1"        # Your forwarding API address
  timeout: 30                                       # Request timeout (seconds)
  debug_mode: false                                 # Debug mode switch

# Scenario Management
scenario:
  file_path: "./scenarios/scenario.json"           # Scenario file path (supports JSON table format)

# Workflow Control Configuration
langgraph:
  max_history_length: 7                            # Number of historical messages passed to forwarding target LLM, controls context length and token consumption
  last_ai_messages_index: 1                       # Index of real AI response (1=last, 2=second-to-last)
  only_forward: false                               # Quick mode switch
  stream_workflow_to_frontend: false               # DRP workflow push switch, by default does not push DRP content to frontend, set to true and import deeproleplay.json regex in SillyTavern if push is needed

# Agent Configuration - Model used by Agent (Recommended Qwen3-235B)
agent:
  model: "qwen/qwen3-235b-a22b-2507"               # Recommended: Qwen3-235B
  base_url: "https://openrouter.ai/api/v1"         # API service address (OpenRouter recommended)
  api_key: "your-api-key"                          # Fill in your API Key
  temperature: 0.1                                 # Generation temperature (0-1)
  max_tokens: 8192                                 # Maximum output token count
  top_p: 0.9                                       # Top-p sampling parameter
  debug: false                                     # Debug mode
  max_iterations: 40                               # Maximum processing rounds
  timeout: 120                                     # Single request timeout

# Server Configuration
server:
  host: "0.0.0.0"
  port: 6666
  reload: false                                    # Hot reload switch
```

### 3. Start Service

```bash
uv run python main.py
```

### 4. Integration and Usage

Change your AI application's (SillyTavern, OpenWebUI, etc.) API endpoint to:
```
http://localhost:6666/v1
```

> 🌟 This project will check if the port is occupied. If it is, it will automatically increment by 1. Therefore, the actual port needs to be checked from the terminal output.

The system will automatically:
1. Intercept conversation requests
2. Execute agent workflow
3. Update scenario state
4. Inject enhanced context into requests
5. Return more accurate role-playing responses

### 5. Package for Distribution

Use PyInstaller to package as executable:

```bash
pyinstaller --name DeepRolePlay --onefile --clean --console --add-data "src;src" --add-data "utils;utils" main.py
```

After packaging, `DeepRolePlay.exe` will be generated in the `dist/` directory, distribute it together with the configuration file to users.

## Supported Models

### 🔌 Full Compatibility with OpenAI Format API
This project uses standard OpenAI API format, supporting all compatible service providers:

#### Recommended Models for Agents
- **🌟 Qwen3-235B** (Strongly Recommended): Only adds 20 seconds response time, excellent role-playing effects

#### Forwarding Target Models
- **💻 Local Ollama**: Fully private deployment, data security
- **🔥 DeepSeek**: High-quality dialogue, low cost
- **⚡ Claude**: Clear logic, strong reasoning ability



## References

The design philosophy of this project is inspired by the following research:

- [Building effective agents](https://www.anthropic.com/research/building-effective-agents) - Anthropic
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph) - LangChain

## License

MIT License