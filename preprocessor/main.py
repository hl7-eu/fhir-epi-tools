import os
import subprocess

# Path to the root folder you want to scan
root_folder = "/Users/joaoalmeida/Desktop/hl7Europe/gravitate/gravitate-health/input/fsh/examples/rawEPI"

# Path to the script you want to run
script_path = "fsh.py"


target_folder = "/Users/joaoalmeida/Desktop/hl7Europe/gravitate/gravitate-health/input/fsh/examples/processedEPI"


for dirpath, dirnames, filenames in os.walk(root_folder):
    for filename in filenames:
        if filename.startswith("composition-"):
            language = filename.split("-")[1]
            target_filename = (
                "pproc_" + language + "_" + filename.split("-")[-1][:-4] + ".fsh"
            )
            print(target_filename)
            # creat bundle file
            bundle_path = os.path.join(dirpath, "Bundle.fsh")

            composition_path = os.path.join(dirpath, filename)

            command = (
                ["python", script_path, composition_path]
                + [os.path.join(target_folder, target_filename)]
                + [bundle_path]
            )
            print(f"Running: {' '.join(command)}")
            subprocess.run(command)
