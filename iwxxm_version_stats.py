import os
import sys
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple

from iwxxm_utils import extractReportInformation
from icao_regions import get_icao_region_name


def _determine_icao_region(report_info: Dict[str, str]) -> Tuple[str, str]:
    """
    Determine ICAO region code (first two letters) and full region name
    from a report info dict returned by extractReportInformation.

    Prefers `aerodrome_designator` for METAR/SPECI/TAF and
    `airspace_designator` for SIGMET/AIRMET. If neither is present,
    returns ("--", "Unknown").
    """
    designator: str = None

    # Try specific designator fields first
    if "aerodrome_designator" in report_info:
        designator = report_info["aerodrome_designator"]
    elif "airspace_designator" in report_info:
        designator = report_info["airspace_designator"]

    # Fallback to unknown if we cannot determine a designator
    if not designator or len(designator) < 2:
        return "--", "Unknown"

    icao_region = designator[:2].upper()
    return icao_region, get_icao_region_name(icao_region)


def analyze_iwxxm_versions(directory_path: str) -> None:
    """
    Analyze IWXXM reports in a directory and print statistics of IWXXM
    versions encountered, organized by ICAO region.

    Args:
        directory_path: Path to a folder containing IWXXM XML files.
    """
    if not os.path.exists(directory_path):
        print(f"Directory '{directory_path}' does not exist.")
        return

    if not os.path.isdir(directory_path):
        print(f"'{directory_path}' is not a directory.")
        return

    files: List[str] = [
        f for f in os.listdir(directory_path)
        if os.path.isfile(os.path.join(directory_path, f))
    ]

    if not files:
        print(f"No files found in directory '{directory_path}'.")
        return

    print(f"Analyzing {len(files)} files in '{directory_path}' for IWXXM version statistics...")
    print("-" * 80)

    # region -> {'total': int, 'versions': Counter}
    region_stats: Dict[str, Dict[str, object]] = defaultdict(lambda: {
        "total": 0,
        "versions": Counter()
    })

    # Track all versions seen for dynamic table header
    all_versions: Set[str] = set()

    files_processed = 0
    files_with_errors = 0
    total_reports = 0

    for index, filename in enumerate(files, 1):
        file_path = os.path.join(directory_path, filename)

        # Progress output for larger folders
        if index % 100 == 0 or index == len(files):
            print(f"Processing file {index}/{len(files)} ({index/len(files)*100:.1f}%): {filename}")

        try:
            with open(file_path, "rb") as f:
                xml_bytes = f.read()

            reports_info = extractReportInformation(xml_bytes, f"file '{filename}'")
            files_processed += 1

            for report_info in reports_info:
                total_reports += 1
                version = report_info.get("iwxxm_version")
                if not version:
                    # Skip if version is missing for any reason
                    continue

                icao_region, _region_name = _determine_icao_region(report_info)
                all_versions.add(version)

                region_stats[icao_region]["total"] += 1
                region_stats[icao_region]["versions"][version] += 1

        except Exception as e:
            files_with_errors += 1
            print(f"Error processing file '{filename}': {e}")
            continue

    print()
    print(f"Files successfully processed: {files_processed}/{len(files)}")
    if files_with_errors:
        print(f"Files with errors: {files_with_errors}")
    print(f"Total IWXXM reports found: {total_reports}")
    print("-" * 80)

    if not total_reports:
        print("No reports found.")
        return

    # Prepare table header with dynamic versions
    versions_sorted: List[str] = sorted(all_versions)

    # Print header
    header_cols = [
        f"{'Region':<8}",
        f"{'Name':<25}",
        f"{'Total':>7}",
    ]
    for v in versions_sorted:
        header_cols.append(f"{v:>10}")  # percentage column per version
    print(" ".join(header_cols))
    print("-" * (8 + 1 + 25 + 1 + 7 + 1 + len(versions_sorted) * 11))

    # Sort regions by code
    for region_code in sorted(region_stats.keys()):
        total_count: int = int(region_stats[region_code]["total"])  # type: ignore[index]
        version_counts: Counter = region_stats[region_code]["versions"]  # type: ignore[index]
        region_name = get_icao_region_name(region_code) if region_code != "--" else "Unknown"

        row = [
            f"{region_code:<8}",
            f"{region_name:<25}",
            f"{total_count:>7}",
        ]

        for v in versions_sorted:
            count_v = version_counts.get(v, 0)
            pct = (count_v / total_count * 100) if total_count > 0 else 0.0
            row.append(f"{pct:>9.1f}%")

        print(" ".join(row))

    print("-" * (8 + 1 + 25 + 1 + 7 + 1 + len(versions_sorted) * 11))

    # Optional: Overall totals per version across all regions
    overall_counter: Counter = Counter()
    overall_total = 0
    for stats in region_stats.values():
        overall_counter.update(stats["versions"])  # type: ignore[index]
        overall_total += stats["total"]  # type: ignore[index]

    overall_row = [
        f"{'ALL':<8}",
        f"{'All Regions':<25}",
        f"{overall_total:>7}",
    ]
    for v in versions_sorted:
        count_v = overall_counter.get(v, 0)
        pct = (count_v / overall_total * 100) if overall_total > 0 else 0.0
        overall_row.append(f"{pct:>9.1f}%")
    print(" ".join(overall_row))


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        directory_path = sys.argv[1]
        if os.path.isdir(directory_path):
            analyze_iwxxm_versions(directory_path)
            sys.exit(0)
        else:
            print(f"'{directory_path}' is not a directory.")
            sys.exit(1)
    else:
        print("Usage:")
        print("  python iwxxm_version_stats.py <directory_path>")
        print("")
        print("Arguments:")
        print("  directory_path      Path to directory containing IWXXM files")
        print("")
        print("Example:")
        print("  python iwxxm_version_stats.py test_data/")
        sys.exit(1)


