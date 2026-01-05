# AI Features - LLM Setup

The Report Generator includes powerful AI features powered by Large Language Models (LLMs). These features run **100% locally** on your machine - no cloud services, no data sharing, completely private.

## Overview

### What Can AI Do?

- **Executive Summaries** - Automatically write 2-3 paragraph report summaries
- **Waveform Analysis** - Identify signal quality issues, noise, and anomalies
- **Pass/Fail Interpretation** - Explain why tests failed and suggest root causes
- **Interactive Chat** - Ask questions about your data in natural language
- **Key Findings** - Extract the most important observations
- **Recommendations** - Suggest next steps based on results

### Privacy & Security

✅ **100% Local** - AI runs on your computer
✅ **No Internet Required** - Works completely offline
✅ **No Data Sharing** - Your data never leaves your machine
✅ **Open Source Models** - Transparent, auditable

## Supported LLM Services

### 1. Ollama (Recommended)

**Best for:** Most users, easy setup, good performance

- Free and open source
- Simple one-command installation
- Large model library
- Good performance on consumer hardware

### 2. LM Studio

**Best for:** Users who want a GUI for model management

- Free with intuitive GUI
- Visual model browser
- Easy model switching
- Performance monitoring

### 3. OpenAI API

**Best for:** Users who want cloud-based AI (not private)

- Most powerful models
- Requires API key and internet
- Pay per use
- Data sent to OpenAI servers

### 4. Custom Endpoints

**Best for:** Advanced users with custom setups

- Any OpenAI-compatible API
- LocalAI, vLLM, Text Generation WebUI
- Self-hosted solutions

## Quick Start: Ollama

### Step 1: Install Ollama

**Download Ollama:**

- Visit [https://ollama.com](https://ollama.com)
- Download for your platform (Windows, macOS, Linux)
- Run the installer

**Verify Installation:**

```bash
# Check that Ollama is running
ollama --version
```

### Step 2: Download a Model

```bash
# Recommended: Llama 3.2 (3B) - Fast, good quality
ollama pull llama3.2

# Alternative: Mistral (7B) - Slower but more capable
ollama pull mistral

# Check downloaded models
ollama list
```

### Step 3: Configure Report Generator

1. **Launch Report Generator**

   ```bash
   siglent-report-generator
   ```

2. **Open LLM Settings**
   - Click **Settings** → **LLM Configuration...**

3. **Select Ollama Tab**
   - Port: `11434` (default)
   - Model: `llama3.2` (or whatever you downloaded)

4. **Test Connection**
   - Click **"Test Connection"**
   - Should show: "Successfully connected to llama3.2 at http://localhost:11434/v1"

5. **Save**
   - Click **"Save"**
   - The AI Assistant sidebar will activate

### Step 4: Try It Out!

1. Import some waveform data
2. Fill in metadata
3. Click **"Generate Summary"** in the AI Assistant panel
4. Watch the AI analyze your data!

## Setup Guide: LM Studio

### Step 1: Install LM Studio

**Download:**

- Visit [https://lmstudio.ai](https://lmstudio.ai)
- Download for your platform
- Install and launch

### Step 2: Download a Model

1. **Open LM Studio**
2. **Go to "Search"** tab
3. **Search for a model:**
   - `llama-3.2-3b` - Fast, lightweight
   - `mistral-7b` - Good balance
   - `llama-3.1-8b` - Higher quality
4. **Click "Download"**
5. **Wait for download** (models are large, 2-15 GB)

### Step 3: Start Local Server

1. **Go to "Local Server"** tab
2. **Select your model** from the dropdown
3. **Click "Start Server"**
4. **Note the port** (usually 1234)

### Step 4: Configure Report Generator

1. **Launch Report Generator**

2. **Settings → LLM Configuration**

3. **Select "LM Studio" Tab**
   - Port: `1234` (or your port)
   - Model: `local-model` (or your model name)

4. **Test Connection** → **Save**

## Setup Guide: OpenAI (Cloud)

!!! warning "Privacy Notice"
OpenAI API sends your data to OpenAI's servers. Not recommended for sensitive data.

### Step 1: Get API Key

1. **Visit** [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. **Sign in** or create account
3. **Click "Create new secret key"**
4. **Copy the key** (starts with `sk-...`)
5. **Save it securely** - you won't see it again!

### Step 2: Configure Report Generator

1. **Settings → LLM Configuration**

2. **Select "OpenAI" Tab**
   - API Key: `sk-your-api-key-here`
   - Model: `gpt-4` (or `gpt-3.5-turbo` for lower cost)

3. **Test Connection** → **Save**

## Using AI Features

### Generate Executive Summary

**What it does:** Creates a 2-3 paragraph summary of your test results

**How to use:**

1. Import waveforms and measurements
2. Fill in metadata
3. Click **"Generate Summary"** in AI Assistant panel
4. Wait 5-30 seconds
5. The summary appears in the chat

**Then what:**

- The summary is automatically added to your report
- You can edit it if needed
- It appears in the "Executive Summary" section

**Example output:**

> This oscilloscope test evaluated a 5V power supply output under 1A load. The frequency measurement of 1.002 kHz was within acceptable limits (±1%), indicating stable operation. Peak-to-peak voltage of 3.98V also passed criteria. However, the rise time of 125ns exceeded the maximum allowable value of 100ns, resulting in an overall FAIL status. This suggests potential slew rate limitations or capacitive loading affecting edge response.

### Analyze Waveforms

**What it does:** Analyzes signal quality, noise, and integrity

**How to use:**

1. Import waveforms
2. Click **"Analyze Waveforms"**
3. Wait for analysis
4. Read the insights

**What it checks:**

- Signal-to-noise ratio
- Overshoot and ringing
- DC offset and bias
- Edge quality (for digital signals)
- Frequency content

**Example output:**

> The waveform shows good signal integrity overall with minimal noise (SNR ~20dB). However, there is observable overshoot on rising edges reaching approximately 10% of the signal amplitude. This could indicate impedance mismatch or inadequate termination. The DC offset appears centered at 0V as expected. Rise time measurements suggest bandwidth limitations in the signal path.

### Interpret Measurements

**What it does:** Explains pass/fail results and suggests fixes

**How to use:**

1. Import waveforms with measurements
2. Click **"Interpret Measurements"**
3. Review explanations

**Especially useful for:**

- Understanding why a test failed
- Getting troubleshooting suggestions
- Learning what measurements mean

**Example output:**

> **Rise Time (FAILED):** The measured rise time of 125ns exceeds the specification of 100ns. Rise time represents how quickly the signal transitions from low to high state. A slower rise time can be caused by:
>
> - Bandwidth limitations in the amplifier or driver circuit
> - Excessive capacitance on the signal line
> - Insufficient drive current from the source
>
> **Recommended actions:**
>
> 1. Check load capacitance and reduce if possible
> 2. Verify driver IC specifications match requirements
> 3. Consider using a faster edge-rate driver
> 4. Reduce trace lengths and parasitic capacitance

### Chat Assistant

**What it does:** Answers questions about your test data

**How to use:**

1. Type a question in the chat input
2. Press Enter or click "Send"
3. Wait for AI response
4. Continue the conversation!

**Example questions:**

- "What do these measurements tell us about signal quality?"
- "Why did the frequency measurement fail?"
- "Is this amount of noise acceptable?"
- "What should I test next?"
- "How can I improve the rise time?"
- "Compare CH1 and CH2 - which is better?"

**Tips for good questions:**

- Be specific - reference actual measurements
- Ask one thing at a time
- Provide context if needed
- Follow up for clarification

## Choosing a Model

### Model Comparison

| Model          | Size   | Speed  | Quality | RAM Needed | Best For           |
| -------------- | ------ | ------ | ------- | ---------- | ------------------ |
| llama3.2 (3B)  | 2 GB   | Fast   | Good    | 4-8 GB     | Most users         |
| mistral (7B)   | 4 GB   | Medium | Better  | 8-16 GB    | Better quality     |
| llama3.1 (8B)  | 4.5 GB | Medium | Better  | 8-16 GB    | Technical analysis |
| llama3.1 (70B) | 40 GB  | Slow   | Best    | 48+ GB     | Highest quality    |

### Recommendations by Use Case

**Casual Use / Learning:**

- llama3.2 (3B) - Fast, good enough

**Professional Testing:**

- mistral (7B) or llama3.1 (8B) - Better technical accuracy

**Research / Publications:**

- llama3.1 (70B) - Best quality (requires powerful hardware)

**Limited Hardware (< 8GB RAM):**

- llama3.2 (3B) - Only option

## Advanced Configuration

### Temperature Setting

Controls randomness in AI responses:

- **0.0-0.3** - Very focused, deterministic, technical
- **0.4-0.7** - Balanced (default: 0.7)
- **0.8-1.0** - Creative, varied responses
- **1.0+** - Very creative, less predictable

**Recommendation:** Keep at 0.7 for most uses

### Max Tokens

Maximum length of AI response:

- **500-1000** - Short, concise answers
- **1000-2000** - Standard (default: 2000)
- **2000-4000** - Long, detailed analysis
- **4000+** - Very comprehensive

**Recommendation:** 2000 is usually sufficient

### Timeout

How long to wait for AI response:

- **30s** - Fast models only
- **60s** - Default, works for most
- **120s+** - Slow models or complex questions

**Recommendation:** 60 seconds for most models

## Troubleshooting

### "Could not connect to LLM"

**Check Ollama is running:**

```bash
# Windows/Mac
ollama list

# Linux
systemctl status ollama
```

**Check port:**

```bash
# Test if port is accessible
curl http://localhost:11434/api/tags
```

**Firewall:**

- Allow Ollama through firewall
- Check antivirus isn't blocking it

### "Connection timeout"

**Increase timeout:**

- Settings → LLM Configuration
- Advanced Settings → Timeout
- Try 120 seconds

**Check model:**

- Larger models take longer
- Consider using smaller model

### Slow Response Times

**Normal times:**

- llama3.2 (3B): 5-15 seconds
- mistral (7B): 15-30 seconds
- llama3.1 (70B): 1-3 minutes

**Speed tips:**

- Use smaller model
- Close other applications
- Reduce max tokens
- Use GPU if available (Ollama auto-detects)

### Poor Quality Responses

**Improve quality:**

- Use larger model (mistral or llama3.1)
- Lower temperature (try 0.5)
- Ask more specific questions
- Provide more context in metadata

### Out of Memory

**Reduce memory usage:**

- Use smaller model (llama3.2 3B)
- Close other applications
- Reduce max tokens to 1000
- Restart Ollama service

## System Prompts

The Report Generator uses specialized system prompts to guide the AI:

- **Expert Oscilloscope Technician** - Technical knowledge
- **Report Summary Writer** - Concise, professional summaries
- **Waveform Analyst** - Signal integrity analysis
- **Measurement Interpreter** - Pass/fail explanations
- **Chat Assistant** - Helpful question answering

These are built into the application and optimized for oscilloscope testing.

## Privacy & Data

### What Gets Sent to the LLM

When using AI features, the following data is sent:

- Measurement values and statistics
- Waveform metadata (sample rate, timebase, etc.)
- Pass/fail status and criteria
- Report title and test information

**Not sent:**

- Raw waveform data (too large)
- Images
- Personal information (unless in metadata)
- Company proprietary information (unless in notes)

### With Local LLM (Ollama/LM Studio)

✅ All data stays on your computer
✅ No internet connection required
✅ No third parties involved
✅ Complete privacy

### With Cloud LLM (OpenAI)

⚠️ Data sent to OpenAI servers
⚠️ Subject to OpenAI's privacy policy
⚠️ Use only for non-sensitive data
⚠️ Costs money per API call

## Next Steps

- **Create Templates** - Save AI-enhanced report configurations in the [Template Guide](templates.md)
- **Learn the API** - Automate AI analysis in the [API Reference](api-reference.md)
- **Get Help** - Ask on [GitHub Discussions](https://github.com/little-did-I-know/Siglent-Oscilloscope/discussions)
