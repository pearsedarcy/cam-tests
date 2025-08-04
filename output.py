html_report_script_fixed = dedent("""\
    import os
    import pandas as pd
    from glob import glob

    result_dir = "./results"
    output_html = os.path.join(result_dir, "summary_report.html")
    logs = glob(os.path.join(result_dir, "*.log"))

    summary = []

    for log_file in logs:
        df = pd.read_csv(log_file)
        avg_cpu = df['cpu_percent'].mean()
        max_mem = df['mem_used_mb'].max()
        avg_disk = df['disk_write_kbps'].mean()

        video_file = log_file.replace(".log", ".mp4")
        size_mb = os.path.getsize(video_file) / (1024 * 1024) if os.path.exists(video_file) else 0

        summary.append({
            "Test": os.path.basename(log_file).replace(".log", ""),
            "Avg CPU (%)": round(avg_cpu, 1),
            "Max RAM (MB)": max_mem,
            "Avg Disk Write (KB/s)": round(avg_disk, 1),
            "Video Size (MB)": round(size_mb, 2)
        })

    df_summary = pd.DataFrame(summary)
    df_summary.sort_values("Avg CPU (%)", inplace=True)

    html_table = df_summary.to_html(index=False, border=0, classes="table table-striped")

    html_content = f\"\"\"
    <html>
    <head>
        <title>Raspberry Pi Video Capture Test Summary</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ padding: 2rem; font-family: sans-serif; }}
            h1 {{ margin-bottom: 2rem; }}
            .table {{ width: auto; margin: auto; }}
        </style>
    </head>
    <body>
        <h1>Raspberry Pi Video Capture Test Summary</h1>
        {html_table}
    </body>
    </html>
    \"\"\"

    with open(output_html, "w") as f:
        f.write(html_content)

    print(f"✅ HTML report written to: {output_html}")
""")

# Save the corrected version
html_report_path = os.path.join(output_dir, "generate_html_report.py")
with open(html_report_path, "w") as f:
    f.write(html_report_script_fixed)

html_report_path
