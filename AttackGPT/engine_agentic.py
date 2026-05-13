# Copyright 2026 Netskope, Inc.
"""
Agentic JIT Engine - Replaces smart_generator.py

Gets:
- Objective string from tactics_config.py (via orchestrator)
- Prompt template from objectives.py (based on tactic)

Builds prompt and sends to LLM. Same interface as smart_generator.py.
"""

import requests
import json
import re
import ollama
import boto3
import logging
import threading
import time
import sys
from objectives import get_template, JSON_TEMPLATE_LIGHTWEIGHT
from tactics_config import get_tactic_config
from sandbox import validate_scripts


logger = logging.getLogger('attackgpt')


def agentic_generator(tactic, technique, mitre_id, objective, lang, is_admin, agent_dir, additional_recon=None, max_retries=5, skip_verification=False, persona=None):
    """
    Main function for agentic code generation (replaces smart_generator).

    Args:
        tactic: MITRE tactic (e.g., "discovery")
        technique: Technique name
        mitre_id: MITRE ID
        objective: Objective string OR array of micro-tasks (from tactics_config.py)
                  - String: Simple technique, one LLM call
                  - List: Complex technique, multiple calls + assembly
        lang: Programming language
        is_admin: Admin privilege flag
        agent_dir: Agent directory
        additional_recon: Additional recon data
        max_retries: Max retry attempts
        skip_verification: Skip verification script generation
        persona: Optional persona/role for system message (e.g., "You are a Service Desk technician...")

    Returns:
        dict: {"script": code, "verification_script": verification, "description": ..., "success": bool}
    """
    
    config = get_tactic_config(tactic)

    if config and config.get("implemented"):
        model = config["model"]
        is_commercial = config["commercial"]
    else:
        print(f"[Router] WARNING: Tactic '{tactic}' not implemented. Using default.")
        model = "gpt-5.2"
        is_commercial = True

    print(f"\n[Router] Model Selection:")
    print(f"  Tactic: {tactic}")
    print(f"  Model: {model} ({'Commercial' if is_commercial else 'Open-Source'})")

    
    template = get_template(tactic)

    if not template:
        print(f"[!] ERROR: No template found for tactic '{tactic}'")
        return {
            "script": None,
            "verification_script": None,
            "success": False,
            "error": f"No template for tactic '{tactic}'"
        }

    print(f"\n[Agentic Engine] Generating script for: {technique} ({mitre_id})")

    
    if isinstance(objective, str):
        
        print(f"  Mode: Simple (single objective)")
        result = _generate_simple(template, objective, lang, is_admin, agent_dir, additional_recon, model, max_retries, persona, skip_verification)
    elif isinstance(objective, list):
        
        print(f"  Mode: Complex ({len(objective)} micro-tasks)")
        result = _generate_with_microtasks(template, objective, lang, is_admin, agent_dir, additional_recon, model, max_retries, persona, skip_verification)
    else:
        print(f"[!] ERROR: objective must be string or list, got {type(objective)}")
        return {
            "script": None,
            "verification_script": None,
            "success": False,
            "error": f"Invalid objective type: {type(objective)}"
        }

    
    if skip_verification and result:
        result["verification_script"] = "exit 0"

    return result


def _generate_simple(template, objective, lang, is_admin, agent_dir, additional_recon, model, max_retries, persona=None, skip_verification=False):
    """
    Generate script for simple technique (one objective string).

    Args:
        template: Prompt template from objectives.py
        objective: Single objective string
        model: LLM model name
        max_retries: Max retry attempts
        persona: Optional persona for system message
        skip_verification: Skip sandbox validation

    Returns:
        dict: {"script": code, "verification_script": verification, "description": ..., "success": bool}
    """
    
    is_opensource = model.lower().startswith(("qwen", "llama", "mistral", "codellama", "deepseek"))

    if is_opensource:
        print(f"  [Prompt] Using LIGHTWEIGHT prompt for open-source model {model}")
        prompt = _build_prompt_lightweight(template, objective, lang, is_admin, agent_dir, additional_recon)
    else:
        print(f"  [Prompt] Using FULL prompt for commercial model {model}")
        prompt = _build_prompt(template, objective, lang, is_admin, agent_dir, additional_recon)

    
    if not persona:
        persona = "You are an experienced systems administrator and automation engineer tasked with creating reliable PowerShell scripts for system management and monitoring."

    
    previous_failures = []
    timeout_retries = 0
    max_timeout_retries = 3  

    for attempt in range(1, max_retries + 1):
        print(f"\n[Healing Loop] Attempt {attempt}/{max_retries}")

        # Optional: Uncomment to debug prompts
        """
        if attempt == 1:
             print("\n" + "="*80)
             print("[DEBUG] FULL PROMPT:")
             print("="*80)
             print(prompt)
             print("="*80 + "\n")
        """
        if attempt > 1:
            print(f"  Previous attempt(s) failed. Regenerating with error feedback...")

        
        while timeout_retries < max_timeout_retries:
            response = _send_to_llm(prompt, model, persona)

            
            if response == "TIMEOUT":
                timeout_retries += 1
                print(f"  [!] LLM request timed out - retry {timeout_retries}/{max_timeout_retries}")
                if timeout_retries >= max_timeout_retries:
                    print(f"  [!] Max timeout retries reached")
                    response = None  
                    break
                continue  
            else:
                
                timeout_retries = 0  
                break

        if not response:
            print(f"  [!] LLM API call failed")
            if attempt == max_retries:
                return {
                    "script": None,
                    "verification_script": None,
                    "success": False,
                    "error": "LLM API error after retries"
                }
            continue

        try:
            
            if is_opensource:
                try:
                    
                    result = _parse_json_response(response)
                    main_script = result.get("script", "")
                except Exception:
                    print(f"  [Lightweight] Raw PowerShell detected (no JSON), wrapping...")
                    main_script = response.strip()
                    main_script = re.sub(r'^```(?:powershell|python|ps1|py)?\s*\n', '', main_script, flags=re.MULTILINE)
                    main_script = re.sub(r'\n```\s*$', '', main_script, flags=re.MULTILINE)
                    result = {
                        "script": main_script.strip(),
                        "verification_script": "exit 0",
                        "description": "File encryption script"
                    }
                verification_script = "exit 0" 
            else:
                
                result = _parse_json_response(response)
                main_script = result.get("script", "")
                verification_script = result.get("verification_script", "exit 0")

            if not main_script:
                print(f"  [!] No script generated")
                continue

            print(f"  [✓] Script generated successfully")

            
            logger.info("\n[Generated Code Preview]")
            logger.info(f"  Main Script: {len(main_script)} characters")
            logger.info("\n" + "="*60)
            logger.info("FULL MAIN SCRIPT")
            logger.info("="*60)
            logger.info(main_script)
            logger.info("="*60 + "\n")

            
            if skip_verification:
                print(f"[Agentic Engine] [SKIP] Validation skipped (skip_verification=True)")
                print(f"[Agentic Engine] Returning unvalidated script on attempt {attempt}")
                result["success"] = True
                return result

            
            print(f"[Agentic Engine] Validating generated scripts in sandbox...")
            success, message = validate_scripts(main_script, verification_script, lang=lang, tactic="script")

            if success:
                print(f"\n[Agentic Engine] [PASS] Validation succeeded on attempt {attempt}")
                print(f"[Agentic Engine] Message: {message}")
                print(f"[Agentic Engine] Returning validated scripts")
                result["success"] = True
                return result
            else:
                print(f"\n[Agentic Engine] [FAIL] Validation failed on attempt {attempt}")
                print(f"[Agentic Engine] Reason: {message}")

                
                previous_failures.append({
                    "attempt": attempt,
                    "error": message,
                    "main_script": main_script[:500], 
                    "verification_script": verification_script[:500]
                })

                if attempt < max_retries:
                    print(f"\n[Self-Healing Loop] Feeding error back to LLM for regeneration...")
                    
                    prompt = _build_prompt_with_failures(template, objective, lang, is_admin, agent_dir, additional_recon, previous_failures, use_lightweight=is_opensource)

        except (json.JSONDecodeError, ValueError) as e:
            print(f"  [!] JSON parse error: {e}")
            if attempt == max_retries:
                return {
                    "script": None,
                    "verification_script": None,
                    "success": False,
                    "error": f"JSON parse error after {max_retries} attempts"
                }

    
    print(f"\n{'='*80}")
    print(f"[CAMPAIGN FAILURE] ❌ All {max_retries} attempts exhausted")
    print(f"{'='*80}")
    return {
        "script": None,
        "verification_script": None,
        "success": False,
        "error": f"All {max_retries} validation attempts failed"
    }


def _generate_with_microtasks(template, micro_tasks, lang, is_admin, agent_dir, additional_recon, model, max_retries, persona=None, skip_verification=False):
    """
    Generate script for complex technique using micro-tasks.

    Flow:
        1. For each micro-task: Generate individual script
        2. Assembly: Combine all scripts into one
        3. Verification: Generate verification script

    Args:
        template: Prompt template from objectives.py
        micro_tasks: List of micro-task strings
        model: LLM model name
        max_retries: Max retry attempts
        skip_verification: Skip sandbox validation

    Returns:
        dict: {"script": assembled_code, "verification_script": verification, "description": ..., "success": bool}
    """
    collected_scripts = []

    
    for idx, task in enumerate(micro_tasks, 1):
        print(f"  Micro-task {idx}/{len(micro_tasks)}: {task[:60]}...")

        prompt = _build_prompt(template, task, lang, is_admin, agent_dir, additional_recon)

        
        for attempt in range(1, max_retries + 1):
            response = _send_to_llm(prompt, model, persona)

            if not response:
                print(f"    [!] LLM API call failed (attempt {attempt}/{max_retries})")
                if attempt == max_retries:
                    return {
                        "script": None,
                        "verification_script": None,
                        "success": False,
                        "error": f"Failed to generate micro-task {idx} after retries"
                    }
                continue

            try:
                result = _parse_json_response(response)
                script = result.get("script", "")

                if script:
                    collected_scripts.append(script)
                    print(f"    [✓] Micro-task {idx} generated ({len(script)} chars)")
                    break
            except (json.JSONDecodeError, ValueError) as e:
                print(f"    [!] JSON parse error: {e} (attempt {attempt}/{max_retries})")
                if attempt == max_retries:
                    return {
                        "script": None,
                        "verification_script": None,
                        "success": False,
                        "error": f"Failed to parse micro-task {idx} response"
                    }


    print(f"\n  [*] Assembling {len(collected_scripts)} micro-task scripts...")
    assembly_prompt = _build_assembly_prompt(template, collected_scripts, lang)

    for attempt in range(1, max_retries + 1):
        response = _send_to_llm(assembly_prompt, model)

        if not response:
            print(f"  [!] Assembly API call failed (attempt {attempt}/{max_retries})")
            if attempt == max_retries:
                return {
                    "script": None,
                    "verification_script": None,
                    "success": False,
                    "error": "Failed to assemble scripts after retries"
                }
            continue

        try:
            result = _parse_json_response(response)
            assembled_script = result.get("script", "")

            if assembled_script:
                print(f"  [✓] Assembly complete ({len(assembled_script)} chars)")

                
                result["success"] = True
                return result
        except (json.JSONDecodeError, ValueError) as e:
            print(f"  [!] Assembly parse error: {e} (attempt {attempt}/{max_retries})")
            if attempt == max_retries:
                return {
                    "script": None,
                    "verification_script": None,
                    "success": False,
                    "error": "Failed to parse assembly response"
                }

    
    return {
        "script": None,
        "verification_script": None,
        "success": False,
        "error": "Unknown error in micro-task generation"
    }


def _build_prompt(template, objective, lang, is_admin, agent_dir, additional_recon):
    """
    Build prompt from template and objective.

    Args:
        template: Prompt template from objectives.py
        objective: Objective string from tactics_config.py
        lang: Programming language
        is_admin: Admin flag
        agent_dir: Agent directory path
        additional_recon: Additional reconnaissance data

    Returns:
        str: Complete prompt for LLM
    """
    json_template = template["json_template"]

    
    context_str = ""

    
    privilege_level = "Administrator/Root" if str(is_admin).lower() in ['true', '1', 'yes'] else "Standard User"
    context_str += f"\nCurrent Privilege Level: {privilege_level}\n"

    
    if agent_dir:
        context_str += f"Agent Location: {agent_dir}\n"

    
    if additional_recon:
        context_str += "\nEnvironment Context:\n"
        for key, value in additional_recon.items():
            
            if key == 'previous_results' and isinstance(value, dict):
                context_str += f"\nPrevious Technique Results (use if relevant):\n"
                context_str += json.dumps(value, indent=2) + "\n"
            else:
                context_str += f"- {key}: {value}\n"

    
    prompt = f"""{objective}
{context_str}
{json_template}"""

    return prompt


def _build_prompt_lightweight(template, objective, lang, is_admin, agent_dir, additional_recon):
    """
    Build LIGHTWEIGHT prompt for open-source models (Qwen) - removes bloat.

    Open-source models work better with concise, focused prompts.
    This version strips out verbose context that confuses smaller models.

    Args:
        template: Prompt template from objectives.py
        objective: Objective string from tactics_config.py
        lang: Programming language
        is_admin: Admin flag
        agent_dir: Agent directory path
        additional_recon: Additional reconnaissance data

    Returns:
        str: Minimal prompt for LLM
    """
    
    context_str = ""

    
    privilege_level = "Administrator" if str(is_admin).lower() in ['true', '1', 'yes'] else "Standard User"
    context_str += f"\nPrivilege Level: {privilege_level}\n"

    prompt = f"""{objective}
{context_str}
{JSON_TEMPLATE_LIGHTWEIGHT}"""

    return prompt


def _build_prompt_with_failures(template, objective, lang, is_admin, agent_dir, additional_recon, previous_failures, use_lightweight=False):
    """
    Build prompt with error feedback from previous failed attempts.

    Args:
        template: Prompt template from objectives.py
        objective: Objective string from tactics_config.py
        lang: Programming language
        is_admin: Admin flag
        agent_dir: Agent directory path
        additional_recon: Additional reconnaissance data
        previous_failures: List of previous failed attempts with error messages
        use_lightweight: Use lightweight prompt for open-source models

    Returns:
        str: Complete prompt for LLM with error feedback
    """
    
    if use_lightweight:
        base_prompt = _build_prompt_lightweight(template, objective, lang, is_admin, agent_dir, additional_recon)
    else:
        base_prompt = _build_prompt(template, objective, lang, is_admin, agent_dir, additional_recon)

    
    failure_feedback = "\n\n### PREVIOUS ATTEMPTS FAILED - PLEASE FIX\n"
    failure_feedback += "Your previous script(s) failed validation. Learn from these errors:\n\n"

    for failure in previous_failures:
        failure_feedback += f"**Attempt {failure['attempt']}:**\n"
        failure_feedback += f"Error: {failure['error']}\n"
        failure_feedback += f"Script that failed (truncated):\n```\n{failure['main_script']}\n```\n\n"

    failure_feedback += "**ACTION REQUIRED:** Analyze the errors above and generate a corrected script that will pass validation.\n"

    
    prompt_parts = base_prompt.split("Return this exact JSON structure:")
    if len(prompt_parts) == 2:
        return prompt_parts[0] + failure_feedback + "\n\nReturn this exact JSON structure:" + prompt_parts[1]
    else:
        
        return base_prompt + failure_feedback


def _build_assembly_prompt(template, scripts, lang):
    """
    Build prompt for assembling multiple scripts into one.

    Args:
        template: Prompt template from objectives.py
        scripts: List of script strings to assemble
        lang: Programming language

    Returns:
        str: Complete assembly prompt for LLM
    """
    json_template = template["json_template"]

    
    scripts_str = "\n\n".join([f"Script {i+1}:\n{script}" for i, script in enumerate(scripts)])

    prompt = f"""Task: Combine the following {len(scripts)} scripts into ONE cohesive, production-ready {lang} script.

{scripts_str}

Requirements:
- Combine all scripts into a single, working script
- Ensure proper error handling throughout
- Remove duplicate code and redundant checks
- Add comments to explain each section
- Make it production-ready and efficient
- The final script should execute all tasks in logical order

{json_template}"""

    return prompt


def _send_to_llm(prompt, model, persona=None):
    """
    Send prompt to LLM API (OpenAI, Claude API, or Ollama).

    Args:
        prompt: The prompt to send
        model: Model name (e.g., "gpt-5.2", "claude-opus-4", "qwen3")
        persona: Optional persona for system message

    Returns:
        str: LLM response content (or None if failed)
    """
    
    is_local = model.lower().startswith(("qwen", "llama", "mistral", "codellama", "deepseek", "phi"))
    is_claude = model.lower().startswith("claude")

    print(f"  [LLM Router] Model: {model}, Is Claude: {is_claude}, Is Local: {is_local}")

    if is_local:
        
        return _send_to_ollama(prompt, model, persona)
    elif is_claude:
        
        return _send_to_anthropic(prompt, model, persona)
    else:
        
        return _send_to_openai(prompt, model, persona)


def _send_to_openai(prompt, model, persona=None):
    """
    Send prompt to OpenAI API.

    Args:
        prompt: The prompt to send
        model: Model name
        persona: Optional persona for system message

    Returns:
        str: LLM response content (or None if failed)
    """
    import os
    api_key = os.environ.get('OPENAI_API_KEY')

    if not api_key:
        print(f"  [LLM ERROR] OPENAI_API_KEY environment variable not set")
        print(f"  [LLM ERROR] Please set: export OPENAI_API_KEY='your-key'")
        return None

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    
    messages = []
    if persona:
        messages.append({"role": "system", "content": persona})
    messages.append({"role": "user", "content": prompt})

    data = {
        "model": model,
        "messages": messages
    }

    stop_spinner = None
    spinner_thread = None

    try:
        print(f"  [LLM] Calling OpenAI {model}...")

        
        stop_spinner = threading.Event()
        spinner_thread = threading.Thread(target=_spinner, args=(stop_spinner, "Generating PowerShell code"))
        spinner_thread.daemon = True
        spinner_thread.start()

        response = requests.post(url, headers=headers, json=data, timeout=980)

        if response.status_code != 200:
            print(f"  [LLM ERROR] Status code: {response.status_code}")
            return None

        result = response.json()

        if "error" in result:
            print(f"  [LLM ERROR] {result['error']}")
            return None

        content = result["choices"][0]["message"]["content"]
        print(f"  [✓] Code generated successfully")
        return content

    except requests.exceptions.Timeout:
        print(f"  [LLM ERROR] Request timed out after 980 seconds - this is retryable")
        return "TIMEOUT" 
    except Exception as e:
        print(f"  [LLM ERROR] {str(e)}")
        return None
    finally:
        if stop_spinner:
            stop_spinner.set()
            spinner_thread.join(timeout=1)


def _send_to_anthropic(prompt, model, persona=None):
    """
    Send prompt to Claude API (Anthropic).

    Args:
        prompt: The prompt to send
        model: Model name (e.g., "claude-opus-4", "claude-sonnet-4")
        persona: Optional persona for system parameter

    Returns:
        str: LLM response content (or None if failed)
    """
    
    import os
    api_key = os.environ.get('ANTHROPIC_API_KEY')

    if not api_key:
        print(f"  [LLM ERROR] ANTHROPIC_API_KEY environment variable not set")
        print(f"  [LLM ERROR] Please set: export ANTHROPIC_API_KEY='your-key'")
        return None

    url = "https://api.anthropic.com/v1/messages"

    
    model_id_map = {
        "claude-opus-4": "claude-opus-4-20250514",
        "claude-opus-4.6": "claude-opus-4-20250514",
        "claude-sonnet-4": "claude-sonnet-4-20250514",
        "claude-sonnet-4.5": "claude-sonnet-4-20250514",
        "claude-sonnet-3.5": "claude-3-5-sonnet-20241022",
    }

    model_id = model_id_map.get(model.lower(), "claude-opus-4-20250514")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    
    data = {
        "model": model_id,
        "max_tokens": 4096,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    if persona:
        data["system"] = persona

    stop_spinner = None
    spinner_thread = None

    try:
        print(f"  [LLM] Calling Claude API {model_id}...")

        
        stop_spinner = threading.Event()
        spinner_thread = threading.Thread(target=_spinner, args=(stop_spinner, "Generating PowerShell code"))
        spinner_thread.daemon = True
        spinner_thread.start()

        response = requests.post(url, headers=headers, json=data, timeout=980)

        if response.status_code != 200:
            print(f"  [LLM ERROR] Status code: {response.status_code}")
            print(f"  [LLM ERROR] Response: {response.text[:200]}")
            return None

        result = response.json()

        if "error" in result:
            print(f"  [LLM ERROR] {result['error']}")
            return None

        
        if "content" in result and len(result["content"]) > 0:
            content = result["content"][0]["text"]
            print(f"  [✓] Code generated successfully")
            return content
        else:
            print(f"  [LLM ERROR] Unexpected response format")
            return None

    except requests.exceptions.Timeout:
        print(f"  [LLM ERROR] Request timed out after 980 seconds - this is retryable")
        return "TIMEOUT"  
    except Exception as e:
        print(f"  [LLM ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        
        if stop_spinner:
            stop_spinner.set()
            spinner_thread.join(timeout=1)


def _send_to_bedrock(prompt, model):
    """
    Send prompt to Claude via AWS Bedrock.

    Args:
        prompt: The prompt to send
        model: Model name (e.g., "claude-opus-4", "claude-sonnet-4")

    Returns:
        str: LLM response content (or None if failed)
    """
    try:
        print(f"  [LLM] Calling AWS Bedrock {model}...")

        
        bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name='us-east-1'
        )


        model_id_map = {
            "claude-opus-4": "anthropic.claude-opus-4-20250514-v1:0",
            "claude-opus-4.6": "anthropic.claude-opus-4-6-v1",
            "claude-sonnet-4": "anthropic.claude-sonnet-4-20250514-v1:0",
            "claude-sonnet-4.5": "anthropic.claude-sonnet-4-5-20250929-v1:0",
            "claude-sonnet-3.5": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        }

        model_id = model_id_map.get(model.lower(), "anthropic.claude-opus-4-20250514-v1:0")

        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )

        response_body = json.loads(response['body'].read())

        if "content" in response_body and len(response_body["content"]) > 0:
            content = response_body["content"][0]["text"]
            return content
        else:
            print(f"  [LLM ERROR] Unexpected Bedrock response format")
            return None

    except Exception as e:
        print(f"  [LLM ERROR] Bedrock error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def _spinner(stop_event, message="Synthesizing payload"):
    """
    Display a loading spinner while waiting for LLM response.

    Args:
        stop_event: threading.Event to signal when to stop
        message: Message to display alongside spinner
    """
    spinners = ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷']
    idx = 0
    start_time = time.time()

    while not stop_event.is_set():
        elapsed = int(time.time() - start_time)
        sys.stdout.write(f"\r  [Synthesizing] {spinners[idx % len(spinners)]} {message}... ({elapsed}s elapsed)")
        sys.stdout.flush()
        idx += 1
        time.sleep(0.1)
    sys.stdout.write('\r' + ' ' * 100 + '\r')
    sys.stdout.flush()


def _send_to_ollama(prompt, model, persona=None):
    """
    Send prompt to Ollama using ollama library.

    Args:
        prompt: The prompt to send
        model: Model name (e.g., "qwen3", "llama3")
        persona: Optional persona (prepended to prompt for local models)

    Returns:
        str: LLM response content (or None if failed)
    """
    try:
        print(f"  [LLM] Calling Ollama {model}...")
        client = ollama.Client()

        
        if persona:
            full_prompt = f"{persona}\n\n{prompt}"
        else:
            full_prompt = prompt

        
        stop_spinner = threading.Event()
        spinner_thread = threading.Thread(target=_spinner, args=(stop_spinner, "Generating PowerShell code"))
        spinner_thread.daemon = True
        spinner_thread.start()

        try:
            
            response = client.generate(model=model, prompt=full_prompt)
            response_content = response['response']
            return response_content
        finally:
            
            stop_spinner.set()
            spinner_thread.join(timeout=1)
            print(f"  [✓] Code generated successfully")

    except Exception as e:
        print(f"  [LLM ERROR] Ollama error: {str(e)}")
        print(f"  [LLM ERROR] Make sure Ollama is running and model '{model}' is installed")
        print(f"  [LLM ERROR] Install with: 'ollama pull {model}'")
        return None


def _parse_json_response(response):
    """
    Parse JSON from LLM response (handles extra text).

    Args:
        response: LLM response string

    Returns:
        dict: Parsed JSON with cleaned script content

    Raises:
        ValueError: If no valid JSON found
    """
    
    try:
        result = json.loads(response)
    except json.JSONDecodeError:
        
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
        else:
            raise ValueError("No valid JSON found in response")

    
    if "script" in result and isinstance(result["script"], str):
        script = result["script"]
        script = re.sub(r'^```(?:powershell|python|ps1|py)?\s*\n', '', script, flags=re.MULTILINE)
        script = re.sub(r'\n```\s*$', '', script, flags=re.MULTILINE)
        result["script"] = script.strip()

    return result



smart_generator = agentic_generator
