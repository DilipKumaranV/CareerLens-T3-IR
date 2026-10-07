"""Generate the three FICTIONAL demo resume PDFs in docs/demo-resumes/ (needs: pip install reportlab).
Names, companies and contact details are invented; e-mail uses example.com and phone numbers use the 555-01xx range."""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).resolve().parents[1] / "docs" / "demo-resumes"
ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=20, leading=24, alignment=0, spaceAfter=2)
SUB = ParagraphStyle("sub", parent=ss["Normal"], fontSize=11.5, leading=15, textColor=colors.HexColor("#2f4bd8"), spaceAfter=2)
SMALL = ParagraphStyle("small", parent=ss["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#555555"))
SEC = ParagraphStyle("sec", parent=ss["Heading2"], fontSize=11, leading=14, spaceBefore=10, spaceAfter=3, textColor=colors.HexColor("#18202e"))
BODY = ParagraphStyle("body", parent=ss["Normal"], fontSize=10, leading=13.5)
BUL = ParagraphStyle("bul", parent=BODY, leftIndent=12, bulletIndent=2)

def build(filename, name, headline, email, phone, summary, skills, jobs, education, extra=None):
    OUT.mkdir(parents=True, exist_ok=True)
    def footer(c, d):
        c.saveState(); c.setFont("Helvetica-Oblique", 7.5); c.setFillColor(colors.HexColor("#777777"))
        c.drawString(18 * mm, 10 * mm, "DEMO PROFILE: fictional candidate created for CareerLens testing. Not a real person."); c.restoreState()
    doc = SimpleDocTemplate(str(OUT / filename), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"{name} - Resume (demo)", author="CareerLens demo")
    s = [Paragraph(name, H1), Paragraph(headline, SUB), Paragraph(f"{email} | {phone} | Springfield (fictional)", SMALL),
         Paragraph("SUMMARY", SEC), Paragraph(summary, BODY), Paragraph("SKILLS", SEC)]
    s += [Paragraph(line, BODY) for line in skills]
    s.append(Paragraph("EXPERIENCE", SEC))
    for title, dates, bullets in jobs:
        s += [Paragraph(f"<b>{title}</b> | {dates}", BODY)] + [Paragraph(b, BUL, bulletText="-") for b in bullets] + [Spacer(1, 4)]
    s += [Paragraph("EDUCATION", SEC)] + [Paragraph(e, BODY) for e in education]
    if extra:
        s += [Paragraph("CERTIFICATIONS", SEC)] + [Paragraph(e, BODY) for e in extra]
    doc.build(s, onFirstPage=footer, onLaterPages=footer)

build("strong-cloud-architect-match.pdf", "Jordan Ellis", "Cloud Engineer / DevOps Engineer", "jordan.ellis@example.com", "+1 (555) 010-0142",
      "Cloud and DevOps engineer with 7 years of experience designing, securing and operating cloud infrastructure for production workloads. "
      "Looking to step up to a Cloud Architect role.",
      ["Cloud: AWS, Azure, Cloud Architecture, Cloud Security, Cloud Migration",
       "Infrastructure: Terraform, Ansible, Infrastructure as Code, Kubernetes, Docker, Linux, Networking",
       "Automation: Python, Bash, Git, Jenkins, CI/CD, GitHub"],
      [("Senior Cloud Engineer - Northwind Cloud Labs (fictional)", "Mar 2022 - Present",
        ["Designed multi-account AWS cloud infrastructure with landing-zone guardrails and centralised logging.",
         "Provisioned environments with HashiCorp Terraform so that every change is reviewed as infrastructure as code.",
         "Run container orchestration on K8s clusters and build Docker images in Jenkins pipelines.",
         "Led the migration of 40 services from on-premises data centres to Azure and AWS."]),
       ("DevOps Engineer - Contoso Systems (fictional)", "Jan 2019 - Feb 2022",
        ["Automated server configuration with Ansible and Python; managed Linux fleets and network segmentation.",
         "Introduced CI/CD with Git and Jenkins, cutting release time from days to hours."])],
      ["B.Sc. Computer Science - Springfield State University (fictional), 2018"],
      ["AWS Certified Solutions Architect - Associate (demo entry)", "HashiCorp Certified: Terraform Associate (demo entry)"])

build("medium-cloud-architect-match.pdf", "Taylor Brooks", "System Administrator / IT Infrastructure Engineer", "taylor.brooks@example.com", "+1 (555) 010-0177",
      "IT infrastructure professional with 5 years of experience running servers, networks and virtualised environments for a mid-sized company. "
      "Interested in moving towards cloud architecture.",
      ["Systems: Linux (RHEL, Ubuntu), Windows Server, Active Directory, System Administration, Virtualization",
       "Networking: TCP/IP, DNS, DHCP, VPN, Firewalls",
       "Scripting and tools: Python, Bash, VMware vSphere, Nagios, Zabbix",
       "Cloud: AWS (EC2, S3, basic IAM)"],
      [("System Administrator - Fabrikam Logistics (fictional)", "Feb 2021 - Present",
        ["Administer 120 Linux and Windows servers, patching, backups and disaster recovery drills.",
         "Operate a VMware vSphere virtualization cluster and maintain the office and branch networks.",
         "Wrote Python and Bash scripts that automate user provisioning and log clean-up.",
         "Supported a small AWS cloud infrastructure (EC2 and S3) used for internal tools."]),
       ("IT Support Engineer - Adventure Works IT (fictional)", "Jul 2019 - Jan 2021",
        ["Resolved server and network incidents and maintained the asset inventory."])],
      ["Diploma in Information Technology - Springfield Technical College (fictional), 2019"])

build("weak-cloud-architect-match.pdf", "Morgan Reyes", "HR Executive", "morgan.reyes@example.com", "+1 (555) 010-0191",
      "Human resources professional with 4 years of experience in recruitment, payroll coordination and employee relations. "
      "Exploring a switch into a technology career.",
      ["HR: HR Operations, Recruitment, Onboarding, Employee Relations, Payroll Processing, Performance Management",
       "Tools: Excel (pivot tables, lookups), PowerPoint, Outlook, HRIS",
       "Soft skills: Communication, Negotiation, Time Management"],
      [("HR Executive - Tailspin Retail (fictional)", "Jan 2022 - Present",
        ["Ran end-to-end recruitment for store and head-office roles and coordinated monthly payroll inputs.",
         "Handled employee relations cases and onboarding for 60 new joiners a year.",
         "Built Excel trackers for headcount and attrition reports."]),
       ("HR Assistant - Wingtip Services (fictional)", "Jun 2020 - Dec 2021",
        ["Maintained employee records and supported recruitment drives and campus hiring."])],
      ["MBA, Human Resources - Springfield Business School (fictional), 2020"])
print("wrote", sorted(p.name for p in OUT.glob("*.pdf")))
