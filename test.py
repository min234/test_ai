from phi.agent import Agent
from phi.model.openai import OpenAIChat
from phi.tools.shell import ShellTools
from phi.tools.file import FileTools
from dotenv import load_dotenv
import os
import json
import subprocess

# ✅ 환경 변수 로드
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("⚠️ `.env` 파일에 `OPENAI_API_KEY`가 설정되지 않았습니다!")

file_list_agent = Agent(
        name="File List Agent",
        model=OpenAIChat(id="gpt-4", api_key=OPENAI_API_KEY),
        tools=[FileTools()],    
        description="디렉터리 내 파일 목록 확인",
        instructions=[
            "Always use the given absolute directory path.",
            "Do not navigate to parent or sibling directories.",
            "Return only files directly in the specified directory."
        ],
        show_tool_calls=True,
        markdown=True,
        debug_mode=True,
    )


language_detection_agent = Agent(
    name="Language Detection Agent",
    model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
    description="언어 판별",
    markdown=True,
    debug_mode=True,
)

language_detection_assistant_agent = Agent(
    name="Language Detection Assistant Agent",
    model=OpenAIChat(id="gpt-4", api_key=OPENAI_API_KEY),
    description="긴 코드를 처리하는 언어 판별 보조 에이전트",
    markdown=True,
    debug_mode=True,
)

language_detection_assistant_last_agent = Agent(
    name="Language Detection Assistant Agent",
    model=OpenAIChat(id="gpt-4", api_key=OPENAI_API_KEY),
    description="긴 코드를 처리하는 언어 판별 보조 에이전트",
    markdown=True,
    debug_mode=True,
)

test_runner_agent = Agent(
    name="Test Runner Agent",
    model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
    tools=[ShellTools()],
    show_tool_calls=True,
    description="테스트 실행",
    markdown=True,
    debug_mode=True,
)

error_analysis_agent = Agent(
    name="Error Analysis Agent",
    model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
    description="오류 분석",
    markdown=True,
    debug_mode=True,
)

test_file_generator_agent = Agent(
    name="Test File Generator Agent",
    model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
    tools=[FileTools()],
    description="테스트 파일 생성",
    markdown=True,
    debug_mode=True,
)

run_test_agent = Agent(
    name="Test Runner Agent",
    model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
    tools=[FileTools()],
    description="코드를 테스트하고 결과를 분석합니다.",
    markdown=True,
    debug_mode=True,
)



# ✅ 1. 파일 목록 확인

def list_all_files(directory: str):
    """
    주어진 디렉터리와 모든 하위 폴더의 파일 목록을 가져옵니다.
    'node_modules', '__pycache__' 폴더 및 특정 확장자 파일은 제외됩니다.
    """
    print(f"🛠️ 디렉터리 '{directory}'와 모든 하위 폴더의 파일 목록을 확인합니다... (node_modules, __pycache__ 제외)")

    if not os.path.exists(directory):
        raise ValueError(f"❌ 경로가 존재하지 않습니다: {directory}")
    if not os.path.isdir(directory):
        raise ValueError(f"❌ 경로가 디렉터리가 아닙니다: {directory}")

    excluded_dirs = {'node_modules', '__pycache__','.pytest_cache','.env'}
    excluded_extensions = {'.pyc', '.pyo', '.log','.md','.TAG','.gitignore','.env'}

    all_files = []
    for root, dirs, files in os.walk(directory):
        # 제외할 디렉토리 무시
        dirs[:] = [d for d in dirs if d not in excluded_dirs]

        # 제외할 파일 확장자 무시
        for file in files:
            file_path = os.path.join(root, file)
            if not any(file_path.endswith(ext) for ext in excluded_extensions):
                all_files.append(file_path)

    print(f"✅ {len(all_files)}개의 파일을 발견했습니다. (제외 디렉토리 및 확장자 적용)")
    return all_files

def split_code_into_chunks(content, chunk_size=1000):
    """
    긴 코드를 지정된 크기(chunk_size)로 나눕니다.
    가능한 경우 줄 단위로 나눠서 코드의 논리적 흐름을 유지합니다.
    """
    lines = content.splitlines()  # 코드를 줄 단위로 나눔
    chunks = []
    current_chunk = []

    current_length = 0
    for line in lines:
        line_length = len(line) + 1  # 줄바꿈 문자 포함
        if current_length + line_length > chunk_size:
            # 현재 청크가 가득 찼으면 저장
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_length = 0

        current_chunk.append(line)
        current_length += line_length

    # 마지막 청크 추가
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks

def detect_languages(file_paths):
    """
    파일 목록에서 언어를 감지하고, 테스트 코드 존재 여부를 최종 판단합니다.
    """
    print("🌐 Language Agent와 보조 에이전트가 파일 언어와 테스트 코드 포함 여부를 감지합니다...")

    if not file_paths:
        print("❌ 파일 목록이 비어 있습니다.")
        return {}

    detected_languages = {}

    for file_path in file_paths:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 초기화
            language_results = []
            has_test_code_results = []
            chunk_results = []

            # 코드가 1000자보다 긴 경우 보조 에이전트를 사용하여 청크로 처리
            if len(content) > 1000:
                chunks = split_code_into_chunks(content)

                for chunk in chunks:
                    response = language_detection_assistant_agent.run(
                        f"""다음 코드를 분석하여 언어를 감지하고, 해당 언어의 테스트 코드 패턴이 포함되었는지 판단해주세요:
                        - 언어: Python, JavaScript, TypeScript, Java 등을 포함합니다.
                        - 테스트 코드 패턴: 아래를 기반으로 감지합니다.
                        - Python: pytest, unittest ('def test_', '@pytest', 'assert').
                        - JavaScript/TypeScript: Jest, Mocha, Jasmine ('describe', 'it', 'test', 'expect').
                        - Java: JUnit ('@Test', 'Assert', 'public void test').

                        코드:
                        {chunk}
                        """,
                        stream=False
                    )

                    if hasattr(response, 'content') and response.content:
                        language = response.content.strip()
                        language_results.append(language)
                        has_test_code = any(
                            keyword in chunk for keyword in [
                                'def test_', '@pytest', 'assert', 
                                'describe', 'it', 'test', '@Test', 
                                'Assert', 'public void test'
                            ]
                        )
                        has_test_code_results.append(has_test_code)
                        chunk_results.append({"chunk": chunk, "response": response.content.strip()})
                    else:
                        language_results.append("언어 감지 실패")
                        has_test_code_results.append(False)

            # 전체 코드에 대해서도 분석
            response = language_detection_agent.run(
                f"""다음 코드를 분석하여 언어를 감지하고, 해당 언어의 테스트 코드 패턴이 포함되었는지 판단해주세요:
                - 언어: Python, JavaScript, TypeScript, Java 등을 포함합니다.
                - 테스트 코드 패턴: 아래를 기반으로 감지합니다.
                - Python: pytest, unittest ('def test_', '@pytest', 'assert').
                - JavaScript/TypeScript: Jest, Mocha, Jasmine ('describe', 'it', 'test', 'expect').
                - Java: JUnit ('@Test', 'Assert', 'public void test').

                코드:
                {content}
                """,
                stream=False
            )

            if hasattr(response, 'content') and response.content:
                language_results.append(response.content.strip())
                has_test_code = any(
                    keyword in content for keyword in [
                        'def test_', '@pytest', 'assert', 
                        'describe', 'it', 'test', '@Test', 
                        'Assert', 'public void test'
                    ]
                )
                has_test_code_results.append(has_test_code)
            else:
                language_results.append("언어 감지 실패")
                has_test_code_results.append(False)

            # 최종 판단: 통합된 데이터로 에이전트 호출
            final_response = language_detection_assistant_last_agent.run(
                f"""다음은 파일의 분석 데이터입니다:
                - 청크 분석 결과: {chunk_results}
                - 전체 코드 분석 결과: {response.content.strip() if hasattr(response, 'content') else "분석 실패"}
                - 청크별 테스트 코드 플래그: {has_test_code_results}

                위 데이터를 기반으로, 이 파일이 테스트 코드를 포함하고 있는지 최종 판단해주세요.
                - 반환: 'True' 또는 'False'
                """,
                stream=False
            )

            # 최종 판단 결과 반영
            if hasattr(final_response, 'content') and final_response.content.strip().lower() in ["true", "false"]:
                has_test_code = final_response.content.strip().lower() == "true"

            # 언어 최빈값 계산
            language_count = {}
            for lang in language_results:
                language_count[lang] = language_count.get(lang, 0) + 1
            final_language = max(language_count, key=language_count.get)

            # 결과 저장
            detected_languages[file_path] = {
                "language": final_language,
                "has_test_code": has_test_code
            }

            print(f"✅ {file_path}: 언어: {final_language}, 테스트 코드 포함 여부: {has_test_code}")

        except Exception as e:
            print(f"❌ {file_path}: 오류 발생 - {e}")

    print(f"✅ Language Agent가 {len(detected_languages)}개의 파일을 분석했습니다.")
    return detected_languages


def check_and_generate_test_files(target_files):
    """
    테스트 파일이 없는 소스 파일에 대해 테스트 파일을 생성합니다.
    - 소스 코드 자체에 테스트 코드가 포함되어 있으면 생성을 건너뜁니다.
    """
    generated_tests = []
    existing_tests = []

    for source_file_path, metadata in target_files.items():
        language = metadata.get('language')
        has_test_code = metadata.get('has_test_code', False)

        if not language:
            print(f"⚠️ 언어가 감지되지 않은 파일: {source_file_path}. 스킵합니다.")
            continue

        if has_test_code:
            print(f"✅ 소스 코드에 테스트 코드가 포함되어 있습니다: {source_file_path}")
            existing_tests.append((source_file_path, language))
            continue

        file_dir = os.path.dirname(source_file_path)
        file_name, file_ext = os.path.splitext(os.path.basename(source_file_path))
        test_file_path = os.path.join(file_dir, f"{file_name}.test{file_ext}")

        if os.path.exists(test_file_path):
            print(f"✅ 기존 테스트 파일 발견: {test_file_path}")
            existing_tests.append((test_file_path, language))
        else:
            generated_file = generate_test_file_from_code(source_file_path, test_file_path)
            if generated_file:
                generated_tests.append((test_file_path, language))

    print(f"✅ 총 {len(generated_tests)}개의 테스트 파일이 생성되었습니다.")
    print(f"✅ 총 {len(existing_tests)}개의 기존 테스트 파일이 확인되었습니다.")
    return generated_tests, existing_tests



def generate_test_file_from_code(source_file_path, test_file_path):
    """
    주어진 원본 코드 파일을 기반으로 AI가 테스트 파일을 생성하고 지정된 경로에 저장합니다.
    """
    print(f"🛠️ {source_file_path} 파일을 분석하여 테스트 파일을 생성합니다.")
    try:
        # 절대 경로로 변환
        source_file_path = os.path.abspath(source_file_path)
        test_file_path = os.path.abspath(test_file_path)
        
        print(f"📂 원본 코드 파일: {source_file_path}")
        print(f"💾 테스트 파일 저장 경로: {test_file_path}")
        
        # 원본 코드 읽기
        if not os.path.exists(source_file_path):
            print(f"❌ 원본 코드 파일이 존재하지 않습니다: {source_file_path}")
            return None
        
        with open(source_file_path, 'r', encoding='utf-8') as f:
            code_content = f.read()
        print("✅ 원본 코드 파일 읽기 성공")
        
        # AI에 테스트 코드 요청
        print("🤖 AI에게 테스트 코드 생성을 요청합니다...")
    
        response = test_file_generator_agent.run(
            f"""다음 코드를 기반으로 테스트 파일을 생성해주세요.
            - 언어: Python, JavaScript, TypeScript, Java 등을 지원합니다.
            - 테스트 프레임워크:
              - Python: pytest
              - JavaScript/TypeScript: Jest
              - Java: JUnit
            - 반환된 내용은 실행 가능한 코드여야 합니다.
            -순수 코드로만 나와야 합니다.
            코드:
            {code_content[:1000]}  # 일부 코드만 전달
            """,
            stream=False
        )
        # RunResponse 객체에서 텍스트 내용 추출
        response_content = response.content if hasattr(response, 'content') else str(response)

        print(f"🔍 AI 응답:\n{response_content}")
        os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(response_content.strip())

        if not response_content or "import pytest" not in response_content.replace("\n", "").replace(" ", ""):
            print("❌ AI가 올바른 pytest 코드를 반환하지 않았습니다.")
            return None

        # 테스트 파일 쓰기
        
        print(f"✅ 테스트 파일이 성공적으로 생성되었습니다: {test_file_path}")

        # 저장된 파일 내용 확인
        with open(test_file_path, 'r', encoding='utf-8') as f:
            saved_content = f.read()
            print("📝 저장된 테스트 파일 내용:")
            print(saved_content)
        print(f"✅ 테스트 파일이 성공적으로 생성되었습니다: {test_file_path}")
        return test_file_path
    
    except Exception as e:
        print(f"❌ 예상치 못한 오류 발생: {e}")
        return None

# ✅ 7. 테스트 파일 실행
def run_test_file(test_file, directory, language):
    """
    테스트 파일을 실행하고 결과를 반환합니다.
    """
    print(f"🚀 Test Runner Agent가 {language} 테스트 파일 {test_file}를 실행합니다...")

    # 언어별 테스트 명령어 매핑
    command = {
        "Python": f"pytest -v {test_file}",
        "JavaScript": "npm test",
        "TypeScript": "npm test",
        "Java": "mvn test"
    }.get(language)

    if not command:
        print(f"⚠️ {language}는 지원되지 않는 언어입니다.")
        return {"stderr": f"Unsupported language: {language}"}

    try:
        # 테스트 실행
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            cwd=directory
        )
        return {"stdout": result.stdout, "stderr": result.stderr}
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류 발생: {e}")
        return {"stderr": str(e)}

# ✅ 에이전트 활용 로직

def analyze_and_run_test(file_path, language):
    """
    파일을 분석하고 테스트를 실행합니다.
    """
    print(f"🔍 파일 분석 중: {file_path}")

    # 테스트 파일이 있는지 확인
    if not os.path.exists(file_path):
        print(f"❌ 파일이 존재하지 않습니다: {file_path}")
        return {"error": "File not found"}

    # 파일 경로와 디렉토리 분리
    directory = os.path.dirname(file_path)
    file_name = os.path.basename(file_path)

    # 테스트 실행
    result = run_test_file(file_name, directory, language)

    # 결과 출력 및 분석
    stdout = result.get("stdout", "")
    stderr = result.get("stderr", "")

    if stderr:
        print(f"⚠️ 테스트 실행 중 오류 발생: {stderr}")
    else:
        print(f"✅ 테스트 실행 결과:\n{stdout}")

    return result


def analyze_errors(error_logs):
    if not error_logs.strip():
        print("✅ 오류 로그가 없습니다.")
        return "No errors detected"
    
    print("🐞 Error Analysis Agent가 오류 로그를 분석합니다...")
    response = error_analysis_agent.run(
        f"다음 오류 로그를 분석하고 원인과 해결책을 제안해주세요:\n\n{error_logs}",
        stream=False
    )

    return response.content.strip() if hasattr(response, 'content') else "분석 실패"


def full_project_analysis(directory):
    """
    주어진 디렉터리의 모든 파일을 확인, 테스트, 분석합니다.
    """
    print("\n📝 **1단계: 파일 목록 확인**")
    file_paths = list_all_files(directory)

    if not file_paths:
        print("❌ 파일 목록이 비어 있습니다. 분석을 종료합니다.")
        return

    print("\n🌐 **2단계: 언어 판별**")
    detected_languages = detect_languages(file_paths)

    if not detected_languages:
        print("❌ 언어를 감지하지 못했습니다. 분석을 종료합니다.")
        return

    print("\n🛠️ **3단계: 테스트 파일 확인 및 생성**")
    generated_tests, existing_tests = check_and_generate_test_files(detected_languages)

    if not generated_tests and not existing_tests:
        print("❌ 테스트 파일이 생성되지 않았고, 기존 테스트 파일도 확인되지 않았습니다. 분석을 종료합니다.")
        return

    print("\n🚀 **4단계: 테스트 실행 및 오류 분석**")
    error_logs = ""
    test_results = {}

    # ✅ 기존 테스트 파일 실행
    for test_file, language in existing_tests:
        print(f"\n🚀 기존 테스트 실행: {test_file} ({language})")
        results = run_test_file(test_file, directory, language)
        test_results[test_file] = {
            "stdout": results.get("stdout", ""),
            "stderr": results.get("stderr", "")
        }
        error_logs += results.get("stderr", "")

    # ✅ 생성된 테스트 파일 실행
    for test_file, language in generated_tests:
        print(f"\n🚀 생성된 테스트 실행: {test_file} ({language})")
        results = run_test_file(test_file, directory, language)
        test_results[test_file] = {
            "stdout": results.get("stdout", ""),
            "stderr": results.get("stderr", "")
        }
        error_logs += results.get("stderr", "")

    print("\n🐞 **5단계: 오류 분석**")
    error_analysis = analyze_errors(error_logs)

    print("\n🎯 **최종 리포트:**")
    report = {
        "file_count": len(file_paths),
        "detected_languages": detected_languages,
        "generated_tests": [test[0] for test in generated_tests],
        "existing_tests": [test[0] for test in existing_tests],
        "test_results": test_results,
        "error_analysis": error_analysis
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


# ✅ 9. 실행
if __name__ == '__main__':
    directory = input("📝 분석 및 테스트할 로컬 프로젝트 디렉터리 경로를 입력하세요: ").strip()
    results = full_project_analysis(directory)
    print("\n🎯 **최종 리포트:**")
    print(json.dumps(results, indent=2, ensure_ascii=False))
