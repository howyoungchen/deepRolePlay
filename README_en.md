# DeepRolePlay: From Deep Research to Deep RolePlay - A Role-Playing System

English | [中文](README.md)

## Project Overview

DeepRolePlay is a deep role-playing system based on LangGraph workflows that completely solves the character forgetting problem of traditional large language models through automated memory management. **Memory Flashback Processing** + **Scenario Update Management** + **Main Conversation Model**, enabling AI to bid farewell to character forgetting and achieve truly coherent role-playing.

## 🚀 Solving Core Pain Points of Role-Playing

<img src="pics/generate.png" alt="DeepRolePlay Demo" width="200">

### 😤 Have You Ever Encountered These Problems?
- 🤖 **AI Suddenly Forgets Character Settings**: A mage suddenly picks up a sword
- 📖 **Inconsistent Plot**: Important plots from yesterday are completely forgotten today
- 💸 **Huge Token Consumption**: Long conversation costs skyrocket, experience interrupted

### ✅ DeepRolePlay's Solutions
- 🧠 **Never Forget**: Automated memory management system, character settings permanently preserved
- 🔄 **Plot Coherence**: Intelligent scenario updates, logical clarity even after millions of conversation rounds  
- 💰 **Cost Control**: Scenario compression technology, long conversation costs reduced by 80%
- 📚 **Intelligent Internet Access**: Integrated Wikipedia encyclopedia, automatic completion of character backgrounds and story settings
- 🗂️ **Structured Management**: JSON table system manages worldview, characters, items, etc., supports dynamic CRUD operations
- ⚡ **Plug and Play**: 5-minute integration, direct use with SillyTavern and other platforms
- 🚀 **Ultra-Fast Response**: Supports any OpenAI style models, except for initial scenario construction, normal dialogue only adds 10 seconds

## 🎯 How to Use

### 💾 Quick Start - Ready-to-Use Version

1. **📦 Extract Software Package**
   - Download the released software package and extract it to a **non-Chinese path**
   - The extracted folder contains: `config.yaml` configuration file + `DeepRolePlay.exe` main program

2. **⚙️ Modify Configuration File**
   
   Edit the `config.yaml` file:

   The configuration file includes detailed beginner's guide, you mainly need to modify the following settings:

   ```yaml
   # API Proxy Configuration - Forwarding Target (Your main chat LLM)
   proxy:
     target_url: "https://api.your-provider.com/v1"    # Change to your API address
     api_key: "Your-Main-LLM-API-key"                  # Change to your API key
   
   # Agent Configuration - Background processing model
   agent:
     model: "deepseek-chat"                            # Any OpenAI format model
     base_url: "https://api.deepseek.com/v1"             # API address
     api_key: "Your-Agent-API-Key"                     # Change to your API key
   ```

3. **🚀 Start Program**
   - Double-click `DeepRolePlay.exe` to start
   - You can see the project running normally in the terminal
   - 🌟 This project will check if the port is occupied. If it is, it will automatically increment by 1. Therefore, the actual port needs to be checked from the terminal output.

4. **🔗 Configure Role-Playing Frontend**
   - In platforms like SillyTavern, OpenWebUI
   - Change `base_url` to: `http://localhost:6666/v1`
   - **Important**: Disable history record limits, must send full history to proxy! (Don't worry about token explosion, max_history_length will control it)

5. **🎭 Start Role-Playing**
   - Immediately enjoy forgetting-free role-playing experience!
   - **Smart Scene Management**: When switching presets and character cards, the system automatically clears old scenarios, no manual operation needed

## 🎛️ Backend Console Features

DeepRolePlay includes a powerful backend management console that allows direct system state and data management through the chat interface.

### 📋 Console Commands

| Command | Function | Description |
|---------|----------|-------------|
| `$drp` | Enter backend mode | Activate console management features |
| `$show` | Display data tables | View all current memory tables (worldview, characters, items, etc.) |
| `$rm` | Clear data | Reset all memory tables and scenario files |
| `$exit` | Exit backend mode | Return to normal role-playing mode |

### 🔧 Usage Instructions

1. **Enter Console**: Send `$drp` in any chat interface
   ```
   User: $drp
   System: Welcome to DeepRolePlay backend mode! Available commands:
           - $rm: Clear all memory tables and scenarios
           - $show: Display current memory tables  
           - $exit: Exit backend mode
   ```

2. **View Data Tables**: Send `$show` to view all currently stored character information
   ```
   User: $show
   System: Current Memory Tables:
           
           [Worldview Table] (2 rows)
           [Character Table] (1 rows)
           [Item Table] (0 rows)
           ...
   ```

3. **Clear Character Data**: Send `$rm` to completely reset role-playing state
   ```
   User: $rm
   System: Memory tables and scenarios directory have been reset successfully.
   ```

4. **Exit Console**: Send `$exit` to return to normal chat mode
   ```
   User: $exit
   System: Exited backend mode successfully.
   ```

### 🎨 ComfyUI Image Generation Support

DeepRolePlay integrates ComfyUI backend for automatic image generation during role-playing:

- **🖼️ Smart Image Generation**: Automatically generates relevant images based on dialogue content and scene descriptions
- **🔧 Custom Workflows**: Supports importing custom ComfyUI workflow JSON files
- **⚡ Asynchronous Processing**: Image generation runs parallel to dialogue without affecting response speed
- **📱 Frontend Optimization**: Automatically adjusts image sizes for optimal transmission efficiency

Configuration example:
```yaml
comfyui:
  enabled: true                           # Enable image generation
  ip: "127.0.0.1"                        # ComfyUI server address
  port: 8188                              # ComfyUI port
  workflow_path: "3rd/comfyui/wai.json"  # Workflow file path
```

## Workflow Principle

Traditional single model problems: **Character Forgetting** → **Plot Breakdown** → **Experience Collapse**

DeepRolePlay's workflow solution:
- 🔍 **Memory Flashback Processing**: Intelligently retrieves historical conversations and external knowledge, automated execution based on LangGraph
- 📝 **Scenario Update Management**: Real-time maintenance of character state and plot coherence, supports tabular data management
- 🗂️ **Table Management System**: Structured storage of worldview, characters, items, etc., supports dynamic CRUD operations
- 🎭 **Main Conversation Model**: Generates character responses based on complete context

## Workflow Process

```
         User Request -> HTTP Proxy Service
                      |
                      v
            [Check if Console Command]
                /              \
            Yes /                \ No
              v                  v
     Backend Console          Trigger Workflow Execution
         |                        |
    Command Parsing           +------+------+
   ($drp/$show/               |             |
    $rm/$exit)                v             v
         |                Memory Flashback  Scenario Update
    Execute Commands          Processing     Processing
    - Display tables          Node           Node
    - Reset data              |             |
    - Mode switching          |        Table Management
         |                    |        (CRUD)
         v                    |             |
    Return Command Result     +------+------+
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


### 2. Start Service

```bash
uv run python main.py
```

### 3. Integration and Usage

Change your AI application's (SillyTavern, OpenWebUI, etc.) API endpoint to:
```
http://localhost:6666/v1
```


> 🌟 This project will check if the port is occupied. If it is, it will automatically increment by 1. Therefore, the actual port needs to be checked from the terminal output.

The system will automatically:
1. Intercept conversation requests
2. Execute workflow
3. Update scenario state
4. Inject enhanced context into requests
5. Return more accurate role-playing responses

### 4. Package for Distribution

Use PyInstaller to package as executable:

```bash
pyinstaller --name DeepRolePlay --onefile --clean --console \
  --add-data "src;src" --add-data "utils;utils" --add-data "config;config" \
  --add-data "3rd;3rd" \
  --hidden-import=locale --hidden-import=codecs \
  main.py
```

After packaging, `DeepRolePlay.exe` will be generated in the `dist/` directory, distribute it together with the configuration file to users.

## Supported Models

### 🔌 Full Compatibility with OpenAI Format API
This project uses standard OpenAI API format, **both background processing models (Agent) and forwarding target models (Proxy) support any OpenAI Style format models**:

#### Supported Service Providers
- **🌟 OpenAI Style**: All APIs supporting OpenAI Style format
- **🔥 OpenRouter**: Aggregates multiple service providers, rich model selection
- **💻 Local Ollama**: Fully private deployment, data security
- **🚀 DeepSeek**: High-quality dialogue, low cost
- **⚡ Claude**: Through OpenRouter or other compatible services
- **🧠 Gemini**: Through compatible interfaces
- **🔧 Self-deployed Models**: Any self-hosted model following OpenAI API format

#### Configuration Description
- **Agent Model**: Used for background memory processing and scenario updates, recommend cost-effective models
- **Proxy Model**: Target model for actual user dialogue, can choose high-quality conversation models
- **Dual Configuration**: Both can use different service providers for flexible cost and effect optimization



## References

The design philosophy of this project is inspired by the following research:

- [Building effective agents](https://www.anthropic.com/research/building-effective-agents) - Anthropic
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph) - LangChain
- [st-memory-enhancement](https://github.com/muyoou/st-memory-enhancement) - muyoou

## License

MIT License