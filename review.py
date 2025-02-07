import requests
import xml.etree.ElementTree as ET
import csv
import json
import re
import requests
from markdownify import markdownify
from requests.exceptions import RequestException
# Import smolagents components
from smolagents import tool, HfApiModel, ToolCallingAgent, ManagedAgent, CodeAgent, DuckDuckGoSearchTool
import argparse
import markdown
from weasyprint import HTML, CSS


def save_to_markdown_table(results, filename="papers_summary.md"):
    """
    Saves the paper summaries as a Markdown table with title in first row.
    """
    with open(filename, "w", encoding="utf-8") as f:
        for paper in results:
            # Write title as a header
            f.write(f"# {paper['Title']} ({paper['Year']})\n\n")
            
            # Create table headers
            f.write("| Category | Content |\n")
            f.write("|----------|----------|\n")
            
            # Write data rows
            sections = [
                ("Main Idea", paper["Main Idea"]),
                ("Pros", paper["Pros"]),
                ("Cons", paper["Cons"]),
                ("Fundamental Ideas", paper["Fundamental Ideas"]),
                ("Related Ideas", paper["Related Ideas"]),
                ("Innovations", paper["Innovations"])
            ]
            
            for section_title, section_content in sections:
                content = section_content
                if isinstance(content, list):
                    content = '<br>'.join([f"• {item}" for item in content])
                f.write(f"| {section_title} | {str(content)} |\n")
            
            # Add space between papers
            f.write("\n---\n\n")

            
def convert_md_to_pdf(md_file="papers_summary.md"):
    """
    Converts markdown to PDF using WeasyPrint with proper bullet point handling
    """

    pdf_file = md_file.split('.')[0] + '.pdf'
    
    # Read markdown file
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Convert markdown to HTML with extended features
    html_content = markdown.markdown(
        md_content,
        extensions=['tables', 'nl2br', 'sane_lists']
    )
    
    # HTML template with CSS for proper formatting
    html_with_css = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                line-height: 1.6;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
                vertical-align: top;
            }}
            th {{
                background-color: #f2f2f2;
            }}
            h1 {{
                color: #333;
                margin-bottom: 20px;
            }}
            ul {{
                margin: 0;
                padding-left: 20px;
            }}
            li {{
                margin-bottom: 5px;
            }}
            td ul {{
                list-style-type: disc;
            }}
        </style>
    </head>
    <body>
    {html_content}
    </body>
    </html>
    """
    
    # Convert to PDF using WeasyPrint
    try:
        HTML(string=html_with_css).write_pdf(
            pdf_file,
            stylesheets=[CSS(string='@page { size: letter; margin: 1in; }')])
        print(f"Successfully converted {md_file} to {pdf_file}")
    except Exception as e:
        print(f"Error converting to PDF: {str(e)}")




def corrector(model, input):
    prompt = [
    {
        "role": "user",
        "content": f"Format it into proper json format, so that it can be seamlessly converted to json: {input}. Only return refined json string and nothing else."
    }]

    response=model(prompt)
    text = response.content

    # Find the first { and last } index
    start = text.find("{")
    end = text.rfind("}") + 1  # +1 to include the closing brace

    # Extract the string including braces
    result = text[start:end]
    return result

@tool
def analyze_abstract(abstract: str) -> str:
    """
    Analyze a paper abstract using the LLM to extract key insights.

    Args:
        abstract: A string containing the paper abstract to be analyzed.

    Returns:
        A JSON-formatted string with keys "main_idea", "pros", "cons", "fundamental_ideas", "related_ideas" and "innovation" representing the analysis.
    """
    prompt = [
    {
        "role": "user",
        "content": f"""You MUST find atleast 3 technical advantages, as well as atleast 3 technical flaws in this approach. Do NOT say 'abstract lacks information' or similar.
        You must also identify fundamental ideas in approach, meaning that techniques in literature that are orchestrated to create the main idea.
        You must also identify related ideas to the main idea, meaning what ideas in literature are similar to technical main idea that is being used to achieve the task.
        You must identify new possible innovations that can improve upon main idea to fill some of the gaps.
        Be creative like Einstein, and Beethoven to find new innovations on main idea that may fill one of the gaps, when filling the 'innovation' section.
# Abstract: {abstract}
# Output ONLY a JSON object:
# {{
#     "main_idea": "brief description",
#     "pros": ["pro1", "pro2",...],
#     "cons": [
#         "specific technical flaw 1 - consider data loss/performance/scalability",
#         "specific technical flaw 2 - consider bottlenecks/memory/training",
#         "specific technical flaw 3 - consider trustworthiness issues",
#         "specific technical flaw 3 - consider mathematical inconsistency",
#     ],
#     "fundamental_ideas": ["idea_1, idea_2",...],
#     "related_ideas": ["related_idea_1", "related_idea_2",...],
#     "innovation": ["innovation_1", "innovation_2",...]      
# }}
# """
    }
]
    
    response = model(prompt)
    return response.content



@tool
def visit_webpage(url: str) -> str:
    """Visits a webpage at the given URL and returns its content as a markdown string.

    Args:
        url: The URL of the webpage to visit.

    Returns:
        The content of the webpage converted to Markdown, or an error message if the request fails.
    """
    try:
        # Send a GET request to the URL
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes

        # Convert the HTML content to Markdown
        markdown_content = markdownify(response.text).strip()

        # Remove multiple line breaks
        markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)

        return markdown_content

    except RequestException as e:
        return f"Error fetching the webpage: {str(e)}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"
    

def fetch_papers(topic: str, max_results: int = 5):
    """
    Fetches papers from arXiv based on a search topic.

    Args:
        topic: The topic to search for.
        max_results: Maximum number of papers to fetch.

    Returns:
        A list of dictionaries, each with keys "title", "abstract", and "year".
    """
    query_url = f"http://export.arxiv.org/api/query?search_query=all:{topic}&max_results={max_results}"
    response = requests.get(query_url)
    root = ET.fromstring(response.text)
    papers = []
    
    for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
        title_elem = entry.find("{http://www.w3.org/2005/Atom}title")
        summary_elem = entry.find("{http://www.w3.org/2005/Atom}summary")
        published_elem = entry.find("{http://www.w3.org/2005/Atom}published")
        
        if title_elem is not None and summary_elem is not None and published_elem is not None:
            title = title_elem.text.strip()
            abstract = summary_elem.text.strip()
            # Extract year from the published date (format: YYYY-MM-DDThh:mm:ssZ)
            year = published_elem.text[:4]
            papers.append({
                "title": title,
                "abstract": abstract,
                "year": year
            })
    return papers



if __name__ == "__main__":

    parser= argparse.ArgumentParser()
    parser.add_argument("--topic", type=str, required=True, help="The topic to search for")
    parser.add_argument("--max_results", type=int, default=1, help="Maximum number of papers to fetch")
    args = parser.parse_args()


    # Define the model (using Hugging Face Inference API)
    model_id = "Qwen/Qwen2.5-Coder-32B-Instruct"
    # model_id = "deepseek-ai/DeepSeek-R1"
    model = HfApiModel(model_id)


    analysis_agent = ToolCallingAgent(
    tools=[analyze_abstract],
    model=model,
    max_steps=1,
    )

    managed_analysis_agent = ManagedAgent(
    agent=analysis_agent,
    name="analysis",
    description="Runs analysis for you",
)
    
    manager_agent = CodeAgent(
    tools=[DuckDuckGoSearchTool(), visit_webpage],
    model=model,
    managed_agents=[managed_analysis_agent],
    additional_authorized_imports=["time", "json", "re", "pandas"],
)


    topic = args.topic
    max_results = args.max_results

    print(f"\nFetching papers for topic: {topic} ...")
    papers = fetch_papers(topic, max_results)
    if not papers:
        print("No papers found for the given topic.")
        exit(1)

    results = []
    for paper in papers:
        print(f"\nAnalyzing paper: {paper['title']}\n")

        task_description = f"Analyze the following abstract: {paper['abstract']} and fill sections for 'main_idea', 'fundamental_ideas', 'related_ideas','innovation', pros', and 'cons' as json string. In this course, search the web to find fundamental and related ideas, as well as get ideas of how to make new innovation on the main idea (be creative). The reultant json string should only contain keys sections for 'main_idea', 'fundamental_ideas', 'related_ideas', 'innovations', 'pros', and 'cons'.\n Note: 'innovations' would refer to new possible improvements to main idea that help solve the cons."
        
        # analysis_output = analysis_agent.run(task_description)
        analysis_output = manager_agent.run(task_description)
        print(f"Raw analysis output:\n{analysis_output}\n")

        analysis_output = corrector(model, analysis_output)
        print(f"Corrected analysis output:\n{analysis_output}\n")


        try:
            analysis_data = json.loads(analysis_output)  # assuming your string is in analysis_output


            
            # Extract all fields
            main_idea = analysis_data["main_idea"]
            fundamental_ideas = analysis_data["fundamental_ideas"]  # strip to remove extra newlines
            related_ideas = analysis_data["related_ideas"]
            innovations = analysis_data["innovations"]
            pros = analysis_data["pros"]
            cons = analysis_data["cons"]
            
            # Print the parsed data
            print(f"Main Idea: {main_idea}\n")
            print(f"Fundamental Ideas: {fundamental_ideas}\n")
            print(f"Related Ideas: {related_ideas}\n")
            print(f"Innovations: {innovations}\n")
            print(f"Pros: {pros}\n")
            print(f"Cons: {cons}")

        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
        except KeyError as e:
            print(f"Missing key in JSON: {e}")

        except Exception as e:
            print(f"Error parsing JSON for paper '{paper['title']}': {e}")
            main_idea = ""
            pros = []
            cons = []
            fundamental_ideas= ""
            related_ideas = ""
            innovations = ""
            

        results.append({
            "Title": paper["title"],
            "Year": paper["year"],
            "Main Idea": main_idea,
            "Pros": pros,
            "Cons": cons,  # Added comma here
            "Fundamental Ideas": fundamental_ideas,
            "Related Ideas": related_ideas,
            "Innovations": innovations
        })

    # csv_filename = "papers_summary.csv"
    # with open(csv_filename, mode="w", newline="", encoding="utf-8") as csvfile:
    #     fieldnames = ["Title", "Year", "Main Idea", "Pros", "Cons", "Fundamental Ideas", "Related Ideas", "Innovations"]
    #     writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    #     writer.writeheader()
    #     for row in results:
    #         writer.writerow(row)

    # print(f"\nCSV summary '{csv_filename}' created successfully!")

    save_to_markdown_table(results, filename=args.topic + ".md")
    convert_md_to_pdf(md_file=args.topic + ".md")