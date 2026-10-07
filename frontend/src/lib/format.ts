export const pct = (x: number | null | undefined, d = 0) => (x === null || x === undefined ? "n/a" : `${(x * 100).toFixed(d)}%`);
export const num = (x: number | null | undefined, d = 3) => (x === null || x === undefined ? "n/a" : x.toFixed(d));
export const money = (j: { salary_year: number | null; salary_hour: number | null }) =>
  j.salary_year ? `$${Math.round(j.salary_year).toLocaleString()} / year (average)` : j.salary_hour ? `$${j.salary_hour.toFixed(0)} / hour (average)` : null;
export const pretty = (s: string) => {
  const K: Record<string, string> = { aws: "AWS", gcp: "GCP", sql: "SQL", nosql: "NoSQL", "power bi": "Power BI", "sql server": "SQL Server", vmware: "VMware", github: "GitHub", gitlab: "GitLab",
    bigquery: "BigQuery", pyspark: "PySpark", postgresql: "PostgreSQL", mysql: "MySQL", mongodb: "MongoDB", javascript: "JavaScript", typescript: "TypeScript", powershell: "PowerShell",
    pytorch: "PyTorch", tensorflow: "TensorFlow", dax: "DAX", sas: "SAS", sap: "SAP", vba: "VBA", html: "HTML", css: "CSS", php: "PHP", ssis: "SSIS", ssrs: "SSRS", spss: "SPSS", redhat: "Red Hat" };
  const k = s.toLowerCase().trim();
  return K[k] ?? k.replace(/\b\w/g, (c) => c.toUpperCase());
};
export const ZONE_LABEL: Record<string, string> = { Title: "Title", Skills: "Skills", Location: "Location", Company: "Company", WorkType: "Work type" };
export const IR_TIP = "IR Relevance Score measures how closely this job matches your search or target-role information need using CareerLens's Information Retrieval pipeline.";
export const FIT_TIP = "Career Fit measures how well this job matches YOUR profile (your skills and current role). It exists only after you provide and confirm a profile.";
