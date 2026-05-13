# Copyright 2026 Netskope, Inc.
"""
Objective prompt templates for AttackGPT.

Replaces prompts.py - contains prompt structures and templates per tactic.

This file is NOT user-facing. Users should configure tactics_config.py.
This file contains the "messy" prompt building logic for LLM interaction.
"""


JSON_TEMPLATE = """
Return this exact JSON structure:
{{
    "script": "complete PowerShell script here using \\n for line breaks",
    "description": "brief description of what this accomplishes",
    "execution_notes": "any special requirements or considerations"
}}


CRITICAL - PowerShell Requirements:
1. DO NOT use PowerShell reserved variables: $Host, $PSVersionTable, $Error, $_, $args, $input, $PSBoundParameters
2. Always ensure parameters are correct types (e.g., Join-Path requires [string] for ChildPath, not $null or numbers)
3. NEVER add colons after variable names - THIS CAUSES CRITICAL SYNTAX ERRORS:
   ❌ WRONG: throw "Error for $k: value"  (WILL CRASH)
   ❌ WRONG: $variable:
   ✓ RIGHT: throw "Error for ${k} value"
   ✓ RIGHT: $variable
4. ALWAYS use -UseBasicParsing with Invoke-WebRequest to prevent interactive prompts
5. Start script with: $ErrorActionPreference = 'Stop'
6. Wrap main logic in try-catch block
7. In catch block: MUST include Write-Error $_.Exception.Message; exit 1
8. On success: exit 0 at the end
9. This ensures script exits with non-zero code on ANY error

MANDATORY Example structure (DO NOT DEVIATE):
$ErrorActionPreference = 'Stop'
try {{
    # Your code here
    # Use safe variable names: $result, $data, $output, $temp, $path, etc.
    # DO NOT use: $Host, $Error, $PSVersionTable, $args, $input, $_
    # Always validate parameter types before passing to cmdlets
    # ...
    exit 0
}} catch {{
    Write-Error $_.Exception.Message  # REQUIRED - DO NOT remove this line
    exit 1
}}

IMPORTANT: Return ONLY the JSON object above. Nothing else.
"""

JSON_TEMPLATE_LIGHTWEIGHT = """
Important: Use try/catch blocks and return exit 0 for success, exit 1 for errors. 
Return ONLY the PowerShell script. No JSON, no markdown, no explanations.
"""


# ============================================================================
# TACTIC: DISCOVERY
# ============================================================================

DISCOVERY_TEMPLATE = {
    "json_template": JSON_TEMPLATE
}


# ============================================================================
# TACTIC: PERSISTENCE
# ============================================================================

PERSISTENCE_TEMPLATE = {
    "json_template": JSON_TEMPLATE
}


# ============================================================================
# TACTIC: COLLECTION
# ============================================================================

COLLECTION_TEMPLATE = {
    "json_template": JSON_TEMPLATE
}


# ============================================================================
# TACTIC: EXFILTRATION
# ============================================================================

EXFILTRATION_TEMPLATE = {
    "json_template": JSON_TEMPLATE
}


# ============================================================================
# TACTIC: CREDENTIAL ACCESS
# ============================================================================

CREDENTIAL_ACCESS_TEMPLATE = {
    "json_template": JSON_TEMPLATE
}


# ============================================================================
# TACTIC: DEFENSE EVASION
# ============================================================================

DEFENSE_EVASION_TEMPLATE = {
    "json_template": JSON_TEMPLATE
}


# ============================================================================
# TACTIC: PRIVILEGE ESCALATION
# ============================================================================

PRIVILEGE_ESCALATION_TEMPLATE = {
    "json_template": JSON_TEMPLATE
}


# ============================================================================
# TACTIC: LATERAL MOVEMENT
# ============================================================================

LATERAL_MOVEMENT_TEMPLATE = {
    "json_template": JSON_TEMPLATE
}


# ============================================================================
# TACTIC: IMPACT
# ============================================================================

IMPACT_TEMPLATE = {
    "json_template": JSON_TEMPLATE
}


# ============================================================================
# TACTIC: COMMAND AND CONTROL
# ============================================================================

COMMAND_AND_CONTROL_TEMPLATE = {
    "json_template": JSON_TEMPLATE
}


# ============================================================================
# TEMPLATE REGISTRY
# ============================================================================

TEMPLATE_REGISTRY = {
    "discovery": DISCOVERY_TEMPLATE,
    "persistence": PERSISTENCE_TEMPLATE,
    "collection": COLLECTION_TEMPLATE,
    "exfiltration": EXFILTRATION_TEMPLATE,
    "credential_access": CREDENTIAL_ACCESS_TEMPLATE,
    "defense_evasion": DEFENSE_EVASION_TEMPLATE,
    "privilege_escalation": PRIVILEGE_ESCALATION_TEMPLATE,
    "lateral_movement": LATERAL_MOVEMENT_TEMPLATE,
    "impact": IMPACT_TEMPLATE,
    "command_and_control": COMMAND_AND_CONTROL_TEMPLATE
}


def get_template(tactic):
    """Get prompt template for a specific tactic"""
    return TEMPLATE_REGISTRY.get(tactic.lower())


def list_templates():
    """List all available tactic templates"""
    return list(TEMPLATE_REGISTRY.keys())


if __name__ == "__main__":
    # Quick test
    print("Available Tactic Templates:")
    print("=" * 60)
    for tactic in TEMPLATE_REGISTRY.keys():
        template = TEMPLATE_REGISTRY[tactic]
        print(f"  {tactic.upper()}")
        print(f"    Context: {template['context'][:60]}...")
        print(f"    Requirements: {len(template['requirements'])} items")
        print()
