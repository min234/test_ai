import os
import json
import subprocess
from phi.agent import Agent
from phi.model.openai import OpenAIChat
from phi.tools.file import FileTools
from dotenv import load_dotenv

# ✅ 환경 변수 로드
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("⚠️ `.env` 파일에 `OPENAI_API_KEY`가 설정되지 않았습니다!")

# ✅ 에이전트 정의
language_detection_agent = Agent(
    name="Language Detection Agent",
    model=OpenAIChat(id="gpt-4", api_key=OPENAI_API_KEY),
    description="언어 판별 및 테스트 코드 유무 확인",
    markdown=True,
    debug_mode=True,
)

test_file_generator_agent = Agent(
    name="Test File Generator Agent",
    model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
    description="테스트 파일 생성",
    markdown=True,
    debug_mode=True,
)

test_code_detection_agent = Agent(
    name="Test Code Detection Agent",
    model=OpenAIChat(id="gpt-4", api_key=OPENAI_API_KEY),
    description="프로젝트 내 테스트 코드 여부를 판단,불필요한 텍스트를 빼고 반드시 순수 json 형식으로만 나오게 해야한다.",
    markdown=True,
    debug_mode=True,
)

error_analyzer_agent = Agent(
    name="Error Analyzer Agent",
    model=OpenAIChat(id="gpt-4", api_key=OPENAI_API_KEY),
    description="테스트 실행 중 발생한 오류를 분석하고 한국어로 요약합니다..",
    markdown=True,
    debug_mode=True,
)

fix_suggestion_agent = Agent(
    name="Fix Suggestion Agent",
    model=OpenAIChat(id="gpt-4", api_key=OPENAI_API_KEY),
    description="오류 메시지 분석 및 간단한 문제 해결",
    instructions=[
        "사용자가 제공한 오류 메시지를 분석하고 문제를 간단히 설명하세요.",
        "만약 문제를 해결할 수 있는 명령어(예: 'pip install flask')가 있다면 명령어를 반환하세요.",
        "결과는 반드시 JSON 형식으로 반환하세요.",
        "불필요한 텍스트를 빼고 반드시 순수 json 형식으로만 나오게 해야한다 "
        "결과 예시:",
        """{
            "solution_type": "command",
            "solution": "pip install flask",
            "description": "Flask 모듈이 누락되었습니다."
        }"""
    ],
    markdown=True,
    debug_mode=True
)

def list_all_files(directory):
    """
    주어진 디렉터리에서 테스트 실행과 관련된 파일 목록을 반환합니다.
    """
    print(f"📂 디렉터리 '{directory}'에서 파일 목록 가져오는 중...")
    excluded_dirs = {'node_modules', '__pycache__', '.git', '.pytest_cache'}
    excluded_extensions = {'.pyc', '.pyo', '.log', '.json'}

    all_files = []

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        for file in files:
            if not any(file.endswith(ext) for ext in excluded_extensions):
                file_path = os.path.join(root, file)
                # 테스트 실행과 관련 없는 파일 필터링
                if not file.endswith(('.py', '.test.py', '.js', '.test.js')):
                    continue
                all_files.append(file_path)
                
    print(f"✅ 총 {len(all_files)}개의 파일이 발견되었습니다.")
    return all_files


def detect_test_code_with_decision(directory):
    """
    디렉터리의 파일들을 분석하여 테스트 코드 여부와 테스트 필요성을 판단합니다.
    """
    test_code_files = []
    decision_records = []  # 각 파일의 판단 기록 저장
    contains_test_code = False

    for file_path in list_all_files(directory):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 에이전트를 사용하여 테스트 코드 여부 판단
            response = test_code_detection_agent.run(
                f"""
                반드시 순수 JSON 형식으로만 결과를 반환하세요.
                불필요한 텍스트나 추가 설명을 포함하지 마세요.
                JSON 형식 외의 텍스트가 응답에 포함될 경우 잘못된 응답으로 간주됩니다.

                ## JSON 형식 예시
                {{
                    "is_test_code": true,
                    "is_test_required": false
                }}

                ## 코드 내용 (최대 500자):
                {content[:500]}
                """,
                stream=False,
            )

            # AI 응답 처리
            response_content = response.content.strip() if hasattr(response, 'content') else ""
            # Markdown 코드 블록 제거
            if response_content.startswith("```json") and response_content.endswith("```"):
                response_content = "\n".join(response_content.splitlines()[1:-1]).strip()

            try:
                response_data = json.loads(response_content)  # JSON 파싱
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON 파싱 실패: {e}. 응답 내용: {response_content}")
                response_data = {"is_test_code": False, "is_test_required": False}  # 기본 값

            # 데이터 추출 및 기록 저장
            is_test_code = response_data.get("is_test_code", False)
            is_test_required = response_data.get("is_test_required", False)

            if is_test_code:
                test_code_files.append(file_path)
                contains_test_code = True

            decision_records.append({
                "file": file_path,
                "is_test_code": is_test_code,
                "is_test_required": is_test_required,
            })

        except Exception as e:
            print(f"❌ 파일 처리 중 오류 발생: {file_path} - {e}")

    # JSON 형식으로 기록 저장 (선택 사항)
    decision_log_path = os.path.join(directory, "test_decision_log.json")
    with open(decision_log_path, 'w', encoding='utf-8') as log_file:
        json.dump(decision_records, log_file, indent=2, ensure_ascii=False)

    return test_code_files, contains_test_code, decision_records




def generate_test_file(source_file_path, language):
    """
    주어진 언어와 원본 파일에 따라 적합한 테스트 파일을 생성합니다.
    """
    try:
        # 원본 코드 읽기
        with open(source_file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()

        print(f"🔍 원본 코드 분석 중: {source_file_path} (언어: {language})")

        # 테스트 파일 이름 설정
        file_name, file_ext = os.path.splitext(os.path.basename(source_file_path))
        test_file_name = f"{file_name}_test{file_ext}"

        # 절대 경로를 원본 파일의 디렉터리 기준으로 설정
        test_file_path = os.path.abspath(os.path.join(os.path.dirname(source_file_path), test_file_name))
        print(f"📁 생성될 테스트 파일 경로: {test_file_path}")

        # 테스트 코드 생성 요청
        response = test_file_generator_agent.run(
            f"""
            아래는 {language}로 작성된 원본 코드입니다. 이 코드를 테스트할 실행 가능한 유닛 테스트 코드를 생성하세요.
            - 테스트 파일 이름: {test_file_name}
            - 테스트 파일 경로: {test_file_path}
            - 원본 코드를 require 해야 합니다.
            - 테스트 코드만 반환해야 하며, Markdown 코드 블록(````javascript` 등)을 포함하지 않아야 합니다.
            - 주석, 설명, 불필요한 텍스트 없이 테스트 코드만 반환하세요.
            - 코드 형식 외의 텍스트가 응답에 포함될 경우 잘못된 응답으로 간주됩니다.
            - 각 언어의 표준 테스트 프레임워크를 사용하세요:
                - Python: pytest를 사용하세요.
                - JavaScript/TypeScript: Jest 또는 Mocha를 사용하세요.
                - Java: JUnit 또는 TestNG를 사용하세요.
            원본 코드:
            {source_code}
            """,
            stream=False
        )

        # AI 응답 처리
        response_content = response.content.strip() if hasattr(response, 'content') else ""
        print(f"📝 AI 응답 내용:\n{response_content}")

        # Markdown 코드 블록 제거
        if response_content.startswith("```") and response_content.endswith("```"):
            response_content = "\n".join(response_content.splitlines()[1:-1]).strip()

        if not response_content.strip() or not any(keyword in response_content for keyword in ["def test_", "import", "assert", "test(", "describe("]):
            raise ValueError(f"AI가 올바른 테스트 코드를 반환하지 않았습니다:\n{response_content}")

        # 테스트 파일 저장
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(response_content)

        print(f"✅ 테스트 파일이 성공적으로 생성되었습니다: {test_file_path}")
        return test_file_path

    except Exception as e:
        print(f"❌ 테스트 파일 생성 중 오류 발생: {e}")
        return None
    

# ✅ 테스트 실행
def run_test_file(test_file, directory, language):
    command = {
        "Python": f"pytest {test_file}",
        "JavaScript": "npm test",
        "TypeScript": "npm test",
        "Java": f"mvn test -Dtest={test_file}",
    }.get(language)

    if not command:
        return {"stdout": "", "stderr": f"⚠️ 지원되지 않는 언어: {language}"}

    try:
        result = subprocess.run(
            command, shell=True, text=True, capture_output=True, cwd=directory, encoding='utf-8', errors='replace'
        )
        with open(f"{test_file}.log", "w", encoding="utf-8") as log_file:
            log_file.write(f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")
        return {"stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    except Exception as e:
        return {"stdout": "", "stderr": str(e)}


# ✅ 오류 분석
def analyze_error(error_message):
    try:
        response = error_analyzer_agent.run(
            f"""다음 오류 메시지를 분석하고 원인을 설명하세요:\n{error_message} 
             """,
            stream=False
        )
        print(f"🛠️ 오류 분석 결과: {response.content}")
        return response.content
    except Exception as e:
        print(f"❌ 오류 분석 중 문제 발생: {e}")
        return None
    
def analyze_and_fix_error(error_message):
    try:
        print(f"🛠️ 오류 분석 중: {error_message}")
        response = fix_suggestion_agent.run(
            f"""
            다음 오류 메시지를 분석하고 문제 원인을 설명한 뒤, 해결 명령어를 제안하세요:
            {error_message}
            """,
            stream=False
        )
        fix_data = json.loads(response.content.strip())
        solution_type = fix_data.get("solution_type", "")
        solution = fix_data.get("solution", "")
        description = fix_data.get("description", "")

        print(f"💡 수정 제안: {description}")
        if solution_type == "command" and solution:
            print(f"💻 명령어 실행 시도 중: {solution}")
            try:
                result = subprocess.run(solution, shell=True, text=True, capture_output=True, check=True)
                print(f"✅ 명령어 실행 성공: {solution}")
                print(f"🔍 출력 결과: {result.stdout}")
            except subprocess.CalledProcessError as e:
                print(f"❌ 명령어 실행 중 오류 발생: {e}")
                print(f"🔍 표준 출력(stdout): {e.stdout}")
                print(f"🔍 표준 에러(stderr): {e.stderr}")
            except Exception as e:
                print(f"❌ 알 수 없는 오류 발생: {e}")
        else:
            print("⚠️ 해결 명령어가 제공되지 않았거나 지원되지 않는 유형입니다.")
    except Exception as e:
        print(f"❌ 오류 분석 및 수정 중 문제 발생: {e}")

        
# ✅ 수정 제안
def suggest_fix(error_message):
    try:
        response = fix_suggestion_agent.run(
            f"""
            다음 오류 메시지를 분석하고 문제 원인을 설명한 뒤, 수정 방법을 구체적으로 제안하세요:
            - 오류 원인 분석
            - 제안된 수정 사항을 명확히 기술 (예: "a - b"는 잘못되었으므로 "a + b"로 수정)
            
            오류 메시지:
            {error_message}
            """,
            stream=False
        )
        print(f"💡 수정 제안: {response.content}")
        return response.content
    except Exception as e:
        print(f"❌ 수정 제안 중 문제 발생: {e}")
        return None

# ✅ 프로젝트 분석 및 테스트
def analyze_and_test_file(file_path):
    """
    단일 파일에 대해 테스트 코드 작성 및 실행 여부를 자동화된 판단에 기반하여 결정합니다.
    """
    print(f"📂 파일 '{file_path}' 분석을 시작합니다...")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 테스트 코드 여부 판단
        print(f"🔍 테스트 코드 여부를 판단 중: {file_path}")
        response = test_code_detection_agent.run(
            f"""
            다음 코드는 테스트 코드 여부를 판단하고, 테스트가 필요한지 여부를 결정해야 합니다.
            반드시 JSON 형식으로 결과를 반환하세요.
            
            ## 코드 내용 (최대 500자):
            {content[:500]}
            
            ## 요구 사항
            {{
                "is_test_code": true/false,    # 파일이 테스트 코드인지 여부
                "is_test_required": true/false  # 테스트 코드 작성 필요 여부
            }}
            """,
            stream=False,
        )

        # AI 응답 처리
        if hasattr(response, 'content') and response.content.strip():
            response_data = json.loads(response.content.strip())
            is_test_code = response_data.get("is_test_code", False)
            is_test_required = response_data.get("is_test_required", False)

            print(f"✅ 테스트 코드 여부: {is_test_code}, 테스트 필요 여부: {is_test_required}")

            if is_test_code:
                print(f"✅ {file_path}는 테스트 코드로 확인되었습니다. 실행만 진행합니다.")
                test_result = run_test_file(file_path, os.path.dirname(file_path), "Python")
            elif is_test_required:
                print(f"🔍 테스트 파일 생성 중: {file_path}")
                test_file = generate_test_file(file_path, "Python")
                if test_file:
                    test_result = run_test_file(test_file, os.path.dirname(test_file), "Python")
                else:
                    test_result = {"stdout": "", "stderr": "테스트 파일 생성 실패"}
            else:
                print(f"⚠️ {file_path}는 테스트 코드 생성이 필요하지 않다고 판단되었습니다.")
                return

            # 테스트 결과에서 에러 확인 및 수정 시도
            if "ERROR" in test_result.get("stdout", "") or test_result.get("stderr"):
                print(f"❌ 테스트 실행 중 오류 발생: {file_path}")
                print("🛠️ 에러 분석 및 수정 시도 중...")
                analyze_and_fix_error(test_result.get("stdout", "") + test_result.get("stderr", ""))

                # 수정 후 다시 실행
                retry_target = test_file if test_file else file_path
                print(f"🔄 수정 후 테스트 재시도: {retry_target}")
                test_result = run_test_file(retry_target, os.path.dirname(retry_target), "Python")

                if "ERROR" in test_result.get("stdout", "") or test_result.get("stderr"):
                    print(f"❌ 수정 후에도 테스트 실패: {retry_target}")
                else:
                    print(f"✅ 수정 후 테스트 성공: {retry_target}")

            print(f"🛠️ 테스트 결과:\n{test_result}")

    except Exception as e:
        print(f"❌ 파일 처리 중 오류 발생: {file_path} - {e}")
        analyze_and_fix_error(str(e))  # 오류 분석 및 자동 해결 시도


def analyze_and_test_project(directory):
    print(f"📂 디렉터리 '{directory}'에서 프로젝트 분석을 시작합니다...")

    all_files = list_all_files(directory)
    print(f"✅ 총 {len(all_files)}개의 파일이 발견되었습니다.")

    test_code_files, contains_test_code, decision_records = detect_test_code_with_decision(directory)
    print(f"📝 테스트 코드 파일: {test_code_files}")
    print(f"🔍 테스트 코드 포함 여부: {contains_test_code}")

    summary = []

    for record in decision_records:
        file_path = record["file"]
        is_test_code = record["is_test_code"]
        is_test_required = record["is_test_required"]

        try:
            print(f"🔍 파일 처리 시작: {file_path}")
            
            if is_test_code:
                print(f"✅ {file_path}는 테스트 코드로 확인되었습니다. 실행만 진행합니다.")
                test_result = run_test_file(file_path, os.path.dirname(file_path), "Python")
            elif is_test_required:
                print(f"🔍 테스트 파일 생성 중: {file_path}")
                test_file = generate_test_file(file_path, "Python")
                if test_file:
                    print(f"✅ {test_file}는 테스트 코드로 확인되었습니다. 실행만 진행합니다.")
                    test_result = run_test_file(test_file, os.path.dirname(file_path), "Python")
                else:
                    test_result = {"stdout": "", "stderr": "테스트 파일 생성 실패"}
            else:
                print(f"⚠️ {file_path}는 테스트 코드 생성이 필요하지 않다고 판단되었습니다.")
                test_result = {"stdout": "", "stderr": "테스트 코드 생성 불필요로 판단됨"}

            if "ERROR" in test_result.get("stdout", "") or test_result.get("stderr"):
                print(f"❌ 테스트 중 오류 발생: {file_path}")
                analyze_and_fix_error(test_result.get("stdout", "") + test_result.get("stderr", ""))

                print(f"🔄 테스트 수정 후 재시도: {test_file if test_file else file_path}")
                retry_test_file = test_file if test_file else file_path
                test_result = run_test_file(retry_test_file, os.path.dirname(retry_test_file), "Python")

            if "ERROR" in test_result.get("stdout", "") or test_result.get("stderr"):
                error_result = suggest_fix(test_result.get("stdout", ""))
                print(f"🔄 에러 문구에 대한 결과 값을 알려줌: {error_result}")

            summary.append({
                "file": file_path,
                "test_file": test_file if is_test_required else None,
                "status": "Test executed",
                "result": test_result
            })

        except Exception as e:
            print(f"❌ 파일 처리 중 오류 발생: {file_path} - {e}")
            analyze_and_fix_error(str(e))
            summary.append({
                "file": file_path,
                "status": "Error",
                "error": str(e),
            })

    print("\n🎯 **최종 요약**")
    for item in summary:
        print(json.dumps(item, indent=2, ensure_ascii=False))


# ✅ 실행
if __name__ == "__main__":
    input_type = input("디렉터리를 검사하려면 '1', 파일만 검사하려면 '2'를 입력하세요: ").strip()
    if input_type == '1':
        project_dir = input("분석할 프로젝트 디렉터리를 입력하세요: ").strip()
        analyze_and_test_project(project_dir)
    elif input_type == '2':
        file_path = input("분석할 파일 경로를 입력하세요: ").strip()
        analyze_and_test_file(file_path)
    else:
        print("⚠️ 잘못된 입력입니다. 프로그램을 종료합니다.")