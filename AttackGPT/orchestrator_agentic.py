# Copyright 2026 Netskope, Inc.
import time
import uuid
import requests
import json
from engine_agentic import agentic_generator as smart_generator
from tactics_config import get_implemented_tactics, get_tactic_config
import os


class Orchestrator:
    """
    ROLE: The Campaign Manager (Strategy).
    Tracks the Attack Cycle and delegates to Router.
    Uses tactics_config.py to determine which tactics to run.
    """
    def __init__(self, context, lang, tactics_to_run=None, techniques_per_tactic=None):
        self.context = context
        self.lang = lang
        self.attack_plan = []  
        self.techniques_per_tactic = techniques_per_tactic or {}
        self.results_store = {}  
        self.discovery_results = self.results_store  

        
        if tactics_to_run is None:
            self.tactics_to_run = get_implemented_tactics()
        else:
            
            self.tactics_to_run = []
            for tactic in tactics_to_run:
                config = get_tactic_config(tactic)
                if config and config.get("implemented"):
                    self.tactics_to_run.append(tactic)
                else:
                    print(f"[WARNING] Tactic '{tactic}' is not implemented. Skipping.")
                    print(f"         Set 'implemented': True in tactics_config.py to enable it.")

    def run_campaign(self):
        """
        The Main Loop: Sequentially plans and generates the full kill chain.
        Runs all tactics specified in self.tactics_to_run (from registry or custom list).

        YIELDS one payload at a time (generator pattern) so server can execute incrementally:
        - Generate Phase 1 → Yield → Server executes → Get result
        - Generate Phase 2 → Yield → Server executes → Get result
        - etc.

        This allows adaptive behavior where later phases can react to earlier results.
        """
        print("[ORCHESTRATOR DEBUG] run_campaign() STARTED - this is a generator function")
        
        if not self.tactics_to_run or len(self.tactics_to_run) == 0:
            print("\n[!] ERROR: No tactics to execute!")
            print("[!] Either:")
            print("    1. No tactics are implemented (set 'implemented': True in tactics_config.py)")
            print("    2. You specified an empty tactics_to_run list")
            print("\nRun 'python list_tactics.py' to see available tactics.")
            return None

        
        print("\n" + "="*60)
        print("TARGET ANALYSIS")
        print("="*60)
        print(f"Hostname: {self.context.get('hostname')}")
        print(f"OS: {self.context.get('os')} {self.context.get('os_version')}")
        print(f"Architecture: {self.context.get('os_arch')}")
        print(f"Privileges: {'Administrator' if self.context.get('isadmin') == 'True' else 'Standard User'}")

        
        additional_recon = self.context.get('additional_recon', {})

        
        temp_folder = self.context.get('temp_folder')
        if temp_folder:
            additional_recon['temp_folder'] = temp_folder

        if additional_recon:
            print("\nEnvironment Intelligence:")
            for key, value in additional_recon.items():
                print(f"  - {key}: {value}")
        print("="*60 + "\n")

        
        print("="*60)
        print("CAMPAIGN PLAN")
        print("="*60)
        print(f"Tactics to Execute: {len(self.tactics_to_run)}")
        total_phases = 0
        for i, tactic in enumerate(self.tactics_to_run, 1):
            config = get_tactic_config(tactic)
            num_techniques = len(config.get('techniques', []))
            total_phases += num_techniques
            print(f"{i}. {tactic.upper()} - {config.get('description', 'N/A')} ({num_techniques} techniques)")
        print(f"\nTotal Phases to Execute: {total_phases}")
        print("="*60 + "\n")

        
        for phase_num, tactic in enumerate(self.tactics_to_run, 1):
            
            techniques = self.techniques_per_tactic.get(tactic, [])

            if not techniques:
                
                config = get_tactic_config(tactic)
                techniques = config.get('techniques', []) if config else []

            
            if not techniques:
                print(f"\n[!] ERROR: No techniques defined for tactic '{tactic}'")
                print(f"[!] Add a 'techniques' array to '{tactic}' in tactics_config.py")
                print(f"[!] Aborting campaign")
                return None

            
            for tech_idx, tech_spec in enumerate(techniques, 1):
                print(f"[*] --- PHASE {phase_num}.{tech_idx}: {tactic.upper()} - {tech_spec['name']} ---")

                try:
                    
                    temp_folder = self.context.get('temp_folder')
                    if tactic.lower() == "persistence":
                        agent_dir = os.path.join(temp_folder, "agent.exe")
                    else:
                        agent_dir = None

                    
                    if self.results_store:
                        additional_recon['previous_results'] = self.results_store
                        print(f"[Orchestrator] Passing previous results to {tactic}: {list(self.results_store.keys())}")

                    
                    code = smart_generator(
                        tactic.lower(),
                        tech_spec['name'],
                        tech_spec['mitre_id'],
                        tech_spec.get('objective', ''),
                        self.lang,
                        self.context.get('isadmin'),
                        agent_dir,
                        additional_recon,
                        skip_verification=tech_spec.get('skip_verification', False),
                        persona=tech_spec.get('persona', None)
                    )

                    
                    if code is None:
                        is_required = tech_spec.get('required', True)  
                        if is_required:
                            print(f"[!] CRITICAL: Failed to generate valid {tech_spec['name']} script after multiple attempts")
                            print(f"[!] Aborting campaign - {tactic} phase failed")
                            return  
                        else:
                            print(f"[!] WARNING: Failed to generate {tech_spec['name']} script, but technique is optional")
                            print(f"[!] Continuing campaign...")
                            continue 

                except Exception as e:
                    print(f"\n[!] EXCEPTION during {tactic} - {tech_spec['name']} generation:")
                    print(f"[!] Error Type: {type(e).__name__}")
                    print(f"[!] Error Message: {str(e)}")
                    print(f"[!] Aborting campaign due to unexpected error\n")
                    import traceback
                    traceback.print_exc()
                    return  

                print(f"[ORCHESTRATOR DEBUG] After try/except, code type: {type(code)}")
                print(f"[ORCHESTRATOR DEBUG] code has 'script': {code.get('script') is not None if isinstance(code, dict) else 'N/A'}")

                payload = {
                    "phase": f"{tactic.capitalize()}-{tech_spec['name']}",
                    "phase_number": f"{phase_num}.{tech_idx}", 
                    "script": code.get('script'),
                    "verification_script": code.get('verification_script'),
                    "mitre": f"{tech_spec['name']} - {tech_spec['mitre_id']}",
                    "reason": tech_spec.get('objective', ''),
                    "description": code.get('description'),
                    "execution_notes": code.get('execution_notes'),
                    "required": tech_spec.get('required', True)  
                }

                print(f"[ORCHESTRATOR DEBUG] About to yield payload")
                print(f"[Orchestrator] Phase ready - yielding to server for execution\n")

                
                yield payload

                print(f"[ORCHESTRATOR DEBUG] Returned from yield, continuing to next phase...")

        
        print("\n" + "="*60)
        print("CAMPAIGN COMPLETED")
        print("="*60)
        print("All phases generated and executed")
        print("="*60)
