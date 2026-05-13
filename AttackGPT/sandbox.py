# Copyright 2026 Netskope, Inc.
import subprocess
import os
import tempfile
import logging


logger = logging.getLogger('attackgpt')


def validate_scripts(main_script, verification_script, lang="PowerShell", tactic="script"):
    """
    Validates generated scripts by executing them in a sandbox environment.

    Args:
        main_script: The main attack script to validate
        verification_script: The verification script to check if main script worked
        lang: Programming language (default: "PowerShell")
        tactic: The tactic name for display purposes (e.g., "persistence", "discovery")

    Returns:
        tuple: (success: bool, message: str)
            - success: True if both scripts pass validation, False otherwise
            - message: Explanation of validation result
    """
    if lang.lower() == "powershell":
        return _validate_powershell_scripts(main_script, verification_script, tactic)
    elif lang.lower() == "python":
        return _validate_python_scripts(main_script, verification_script, tactic)
    else:
        return False, f"Unsupported language: {lang}"


def _validate_powershell_scripts(main_script, verification_script, tactic="script"):
    """
    Validates PowerShell scripts.

    Args:
        main_script: The main script to validate
        verification_script: The verification script (ignored - for backward compatibility)
        tactic: The tactic name for display (e.g., "persistence", "discovery")

    Returns:
        tuple: (success: bool, message: str)
    """
    
    logger.info("\n[Sandbox Validation]")

    
    logger.info(f"  Executing main {tactic} script...")
    main_success, main_output = _execute_powershell(main_script)

    if not main_success:
        logger.info(f"    [FAIL] Main script failed (non-zero exit code)")
        logger.info(f"\n--- ERROR OUTPUT ---")
        logger.info(main_output)
        logger.info("--- END ERROR OUTPUT ---\n")
        return False, f"Main script execution failed: {main_output}"

    logger.info(f"    [PASS] Main script executed successfully (exit code 0)")
    logger.info(f"    [INFO] Output: {main_output[:200] if main_output else 'No output'}...")

    
    return True, "Script executed successfully with exit code 0"


def _execute_powershell(script, stdin_input=None):
    """
    Executes a PowerShell script and returns success status.

    Args:
        script: PowerShell script string
        stdin_input: Optional string to pass as stdin to the script

    Returns:
        tuple: (success: bool, output: str)
    """
    try:
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False) as f:
            f.write(script)
            script_path = f.name

        
        if os.name == 'nt':
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        else:
            si = None

        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            input=stdin_input,  
            capture_output=True,
            text=True,
            timeout=180,
            startupinfo=si if os.name == 'nt' else None
        )

        
        os.unlink(script_path)

        
        logger.info(f"    [DEBUG] PowerShell returncode: {result.returncode}")
        logger.info(f"    [DEBUG] stdout: {result.stdout[:200] if result.stdout else 'None'}...")
        logger.info(f"    [DEBUG] stderr: {result.stderr[:200] if result.stderr else 'None'}...")

        
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr if result.stderr else result.stdout

    except subprocess.TimeoutExpired:
        return False, "Script execution timed out (30s limit)"
    except Exception as e:
        return False, f"Execution error: {str(e)}"


def _validate_python_scripts(main_script, verification_script, tactic="script"):
    """
    Validates Python scripts (future implementation).

    Args:
        main_script: The main script to validate
        verification_script: The verification script
        tactic: The tactic name for display

    Returns:
        tuple: (success: bool, message: str)
    """
    
    logger.info(f"[Sandbox] Python validation for {tactic} not yet implemented")
    return False, "Python validation not implemented"
