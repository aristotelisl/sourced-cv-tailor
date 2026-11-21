"""Find technology names in text, so the validator can check every one is backed by a source."""
import re
from functools import lru_cache

# Common technologies that aren't in the profile at all. If one shows up in a bullet,
# the LLM made it up. (Profile skills and stacks are added to the vocabulary too.)
COMMON_TECH = [
    "Angular", "Vue", "Svelte", "Redux", "MobX", "jQuery", "Webpack", "GraphQL", "gRPC", "WebSockets",
    "Django", "Spring", "Spring Boot", "Rails", "Laravel", "NestJS", "Fastify", "Deno", "Bun",
    "Rust", "Go", "Golang", "Kotlin", "Swift", "Scala", "Ruby", "PHP", "Elixir", "Haskell",
    "MySQL", "MongoDB", "Redis", "Cassandra", "DynamoDB", "Elasticsearch", "Snowflake", "BigQuery", "DuckDB",
    "Kafka", "RabbitMQ", "Airflow", "Spark", "dbt",
    "AWS", "GCP", "Google Cloud", "Kubernetes", "Terraform", "Ansible", "Jenkins", "GitHub Actions",
    "GitLab CI", "CircleCI", "Lambda", "ECS", "EKS", "S3",
    "PyTorch", "TensorFlow", "Keras", "scikit-learn", "Hugging Face", "LangChain", "pandas", "NumPy",
    "Power BI", "Tableau", "Figma", "Storybook", "Jest", "Cypress", "Playwright", "Selenium",
]


def split_skill(item: str) -> list[str]:
    """'Python (Flask, FastAPI)' -> ['Python', 'Flask', 'FastAPI']."""
    return [t.strip() for t in re.split(r"[(),]", item) if t.strip()]


@lru_cache(maxsize=4096)
def term_pattern(term: str, ignore_case: bool) -> re.Pattern:
    return re.compile(rf"(?<![\w.+#-]){re.escape(term)}(?![\w+#]|\.\w)", re.IGNORECASE if ignore_case else 0)


def mentions(text: str, term: str, ignore_case: bool = False) -> bool:
    """Whole-word match. Case-sensitive by default, so English words ("go", "rails", "spark")
    in a CV bullet aren't mistaken for technologies."""
    return bool(term_pattern(term, ignore_case).search(text))


def tech_vocabulary(profile: dict) -> list[str]:
    """Every technology name the validator watches for, longest first."""
    terms: set[str] = set(COMMON_TECH)
    skills = profile.get("skills", {})
    for group in ("strong", "listed", "not_claimed"):
        for item in skills.get(group, []):
            terms.update(split_skill(item))
    for project in profile.get("projects", []):
        for items in (project.get("stack") or {}).values():
            for item in items:
                terms.update(split_skill(item))
    for exp in profile.get("experience", []):
        terms.update(exp.get("stack", []))
        for b in exp.get("bullets", []):
            terms.update(b.get("stack", []))
    # Drop generic words that live in the skills list but aren't technologies.
    terms -= {"RAG", "Agentic workflows", "Prompt Engineering", "profiling tools", "Vite dev proxy"}
    return sorted(terms, key=len, reverse=True)
