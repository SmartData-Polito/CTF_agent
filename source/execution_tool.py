import subprocess
from langchain_core.tools import tool
import shlex
from source.sandbox import LocalSandboxWrapper

def sandbox_execution(sandbox):

    @tool(description="Execute a bash command inside the sandbox")
    def run_command(cmd: str, reason: str = "", timeout: int = 30) -> str:
        print("\n------------------- TOOL CALL -------------------")
        print(f"🔧 run_command called with: {cmd}")
        if reason:
            print(f"📝 Reason: {reason}")
        print("-------------------------------------------------\n")

        if not cmd.strip():
            return "Error: Empty command"

        try:
            result = sandbox.commands.run(
                cmd,
                timeout=timeout,
                user="root"
            )

            stdout = result.stdout or ""
            stderr = result.stderr or ""
            exit_code = getattr(result, "exit_code", "unknown")

            output = (
                f"Exit code: {exit_code}\n\n"
                f"STDOUT\n{stdout}\n\n"
                f"STDERR\n{stderr}"
            )

            # Optional truncation (recommended)
            if len(output) > 30000:
                output = output[:30000] + "\n...[OUTPUT TRUNCATED]"

            return output

        except Exception as e:
            return f"Failed to run command in sandbox: {str(e)}"

    return run_command


def sandbox_python_execution(sandbox):

    @tool(description="Execute Python code inside the sandbox")
    def run_python(python_code: str, reason: str = "", timeout: int = 30) -> str:
        print("\n------------------- TOOL CALL -------------------")
        print(f"🐍 run_python called:")
        print(python_code)
        print(f"📝 Reason: {reason}")
        print("-------------------------------------------------\n")

        if not python_code.strip():
            return "Error: Empty Python code"

        try:
            import uuid

            script_name = f"temp_script_{uuid.uuid4().hex[:8]}.py"
            script_path = script_name

            # Write code to sandbox filesystem
            sandbox.files.write(script_path, python_code)

            # Execute with venv activated
            cmd = f"python3 {script_path}"

            result = sandbox.commands.run(
                cmd,
                timeout=timeout,
                user="root"
            )

            stdout = result.stdout or ""
            stderr = result.stderr or ""
            exit_code = getattr(result, "exit_code", "unknown")

            output = (
                f"Exit code: {exit_code}\n\n"
                f"STDOUT\n{stdout}\n\n"
                f"STDERR\n{stderr}"
            )

            if len(output) > 30000:
                output = output[:30000] + "\n...[OUTPUT TRUNCATED]"

            return output

        except Exception as e:
            return f"Failed to run Python code in sandbox: {str(e)}"

    return run_python

