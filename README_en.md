# DeepRolePlay: Deep Role-Playing System Based on Multi-Agent Architecture

English | [中文](README.md)

## Project Overview

DeepRolePlay is a groundbreaking multi-agent role-playing system that completely solves the character forgetting problem of traditional large language models through Agent collaboration mechanisms.

DeepRolePlay adopts a multi-agent division of labor architecture: **Memory Flashback Agent** + **Scenario Update Agent** + **Main Conversation Model**, enabling AI to bid farewell to character forgetting and achieve truly coherent role-playing.

## 🚀 Solving Core Pain Points of Role-Playing

### 😤 Have You Ever Encountered These Problems?
- 🤖 **AI Suddenly Forgets Character Settings**: A mage suddenly picks up a sword
- 📖 **Inconsistent Plot**: Important plots from yesterday are completely forgotten today
- 💸 **Huge Token Consumption**: Long conversation costs skyrocket, experience interrupted

### ✅ DeepRolePlay's Solutions
- 🧠 **Never Forget**: Agent automatically maintains character memory, settings permanently preserved
- 🔄 **Plot Coherence**: Intelligent scenario updates, logical clarity even after millions of conversation rounds
- 💰 **Cost Control**: Scenario compression technology, long conversation costs reduced by 80%
- 📚 **Intelligent Internet Access**: Integrated Wikipedia, free automatic completion of character backgrounds and story settings
- ⚡ **Plug and Play**: 5-minute integration, direct use with SillyTavern and other platforms

### ⚖️ Trade-offs and Disadvantages

To achieve the above effects, this project has the following costs, please be aware before use:

- ⏱️ **Increased Response Time**: Agent workflow requires additional processing time, overall time consumption may increase by 2-3 times
- 💸 **Initial Token Consumption**: The first few rounds of conversation need to establish scenario state, token consumption may be slightly higher than direct calls
- 🔧 **System Complexity**: Compared to direct LLM calls, requires additional service deployment and maintenance

**Applicable Scenarios**: If you pursue long-term coherent large-scale role-playing experiences and don't mind slightly slower response speeds, these costs are worthwhile.

## 🎯 How to Use

### Super Simple Integration
1. **Start Service**: Run `uv run python main.py`, system starts on port 6666
2. **Change Interface**: In platforms like SillyTavern, OpenWebUI:
   - Change `base_url` to `http://localhost:6666/v1`
   - Keep API Key unchanged (directly passed to backend model)
3. **Start Using**: Immediately enjoy forgetting-free role-playing experience!

### Compatibility Description
- ✅ **Fully Compatible with OpenAI API Format**: All tools supporting OpenAI can be used directly
- ✅ **Support Mainstream Models**: OpenAI GPT, DeepSeek, Claude, local Ollama, etc.
- ✅ **Dual Configuration**: Agent and forwarding target can use different models, flexible cost optimization

## Agent Working Principle

Traditional single model problem: **Character Forgetting** → **Plot Breakdown** → **Experience Collapse**

DeepRolePlay's Agent Solution:
- 🔍 **Memory Flashback Agent**: Intelligently retrieves historical conversations and external knowledge
- 📝 **Scenario Update Agent**: Real-time maintenance of character state and plot coherence
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

## Usage Steps

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

Edit `config/config.yaml` file, **DeepSeek is recommended (best cost-performance)**:

```yaml
# API Proxy Configuration - Forwarding Target
proxy:
  target_url: "https://api.deepseek.com/v1"   # Recommend DeepSeek, low cost and good performance
  api_key: "your-deepseek-api-key"            # DeepSeek API Key
  timeout: 30                                 # Request timeout (seconds)

# Agent Configuration - Model used by Agent  
agent:
  model: "deepseek-chat"                      # Recommend DeepSeek Chat, economical
  base_url: "https://api.deepseek.com/v1"    # Can be different from proxy target
  api_key: "your-deepseek-api-key"            # Can use same or different API Key
  temperature: 0.1                            # Generation temperature (0-1)
  max_iterations: 25                          # Maximum iterations

# Scenario Management
scenario:
  file_path: "./scenarios/scenario.txt"      # Scenario file path
  update_enabled: true                        # Whether to enable automatic updates

# Server Configuration
server:
  host: "0.0.0.0"
  port: 6666
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

The system will automatically:
1. Intercept conversation requests
2. Execute agent workflow
3. Update scenario state
4. Inject enhanced context into requests
5. Return more accurate role-playing responses

## Supported Models

### 🔌 Full Compatibility with OpenAI Format API
This project uses standard OpenAI API format, supporting all compatible service providers:

- **🌟 DeepSeek** (Highly Recommended): Best cost-performance, excellent role-playing effects
- **💻 Local Ollama**: Fully private deployment, data security

### ⚠️ OpenAI Official API Not Recommended
Although fully compatible with OpenAI format, **using OpenAI official service is not recommended**:
- 🔒 **Excessive Safety Policies**: Strict restrictions on role-playing content, affecting experience

## References

The design philosophy of this project is inspired by the following research:

- [Building effective agents](https://www.anthropic.com/research/building-effective-agents) - Anthropic
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph) - LangChain

## License

MIT License