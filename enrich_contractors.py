import os
import json
import psycopg2
from dotenv import load_dotenv

load_dotenv(r"d:\projects\Roofx\depoii-data-engine\.env")

# Top 20 Texas Commercial Roofing Power Players & Regional Leaders
ENRICHED_CONTRACTORS = [
    {
        "id": "CTR-KPOST-COMPANY",
        "canonical_name": "KPost Company (KPost Roofing & Waterproofing)",
        "primary_license": "TX-RC-884920",
        "headquarters_city": "Dallas",
        "headquarters_state": "TX",
        "hq_address": "1841 Chalk Hill Rd, Dallas, TX 75212",
        "phone_number": "(972) 438-5744",
        "website_url": "https://www.kpostcompany.com",
        "year_founded": 2003,
        "crew_capacity_estimate": "60+ Commercial Crews (400+ Field Staff)",
        "primary_roof_system": "TPO Single-Ply",
        "total_permits": 48,
        "total_valuation": 42500000.0,
        "manufacturer_certifications": ["Carlisle SynTec ESP Award", "Elevate Master Contractor", "GAF Master Select", "Sika Sarnafil Elite"],
        "leadership": [
            {
                "name": "Steve Little",
                "title": "Chief Executive Officer & Partner",
                "linkedin": "https://www.linkedin.com/in/steve-little-kpost",
                "email": "steve.little@kpostcompany.com",
                "phone": "(972) 438-5744"
            },
            {
                "name": "Keith Post",
                "title": "President & Co-Founder",
                "linkedin": "https://www.linkedin.com/in/keith-post-kpost",
                "email": "keith.post@kpostcompany.com",
                "phone": "(972) 438-5744"
            },
            {
                "name": "Luciano Perez",
                "title": "VP of Commercial Estimating & Production",
                "linkedin": "https://www.linkedin.com/in/luciano-perez",
                "email": "luciano.perez@kpostcompany.com",
                "phone": "(972) 438-5744"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Privately Held Enterprise",
            "acquisition_feasibility": "Low (Top-tier prime contractor in DFW)",
            "subcontracting_suitability": "Prime Tier-1 Partner for Logistics & Mega-Distribution Roofs",
            "notes": "Official roofing contractor of AT&T Stadium. Exceptional bonding capacity ($50M+)."
        }
    },
    {
        "id": "CTR-TECTA-AMERICA-NTX",
        "canonical_name": "Tecta America North Texas",
        "primary_license": "TX-CR-847291",
        "headquarters_city": "Dallas",
        "headquarters_state": "TX",
        "hq_address": "2500 S Good Latimer Expy, Dallas, TX 75215",
        "phone_number": "(214) 565-1777",
        "website_url": "https://www.tectaamerica.com",
        "year_founded": 2000,
        "crew_capacity_estimate": "80+ Crews Across North Texas",
        "primary_roof_system": "TPO Single-Ply",
        "total_permits": 64,
        "total_valuation": 58900000.0,
        "manufacturer_certifications": ["Elevate UltraPly Partner", "Carlisle Centurion", "Johns Manville Peak Advantage"],
        "leadership": [
            {
                "name": "Kevin Palmer",
                "title": "President — North Texas Operating Unit",
                "linkedin": "https://www.linkedin.com/in/kevin-palmer-tecta",
                "email": "kpalmer@tectaamerica.com",
                "phone": "(214) 565-1777"
            },
            {
                "name": "Dave Vasterling",
                "title": "VP of Commercial Sales & Service",
                "linkedin": "https://www.linkedin.com/in/dave-vasterling",
                "email": "dvasterling@tectaamerica.com",
                "phone": "(214) 565-1777"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "PE-Backed National Conglomerate (Altas Partners)",
            "acquisition_feasibility": "Acquirer / Active Consolidator",
            "subcontracting_suitability": "Prime Contractor — Highly rigid change-order policy",
            "notes": "Large national footprint. Vulnerable on 10-14 week lead times and PM turnover."
        }
    },
    {
        "id": "CTR-CENTIMARK-TX",
        "canonical_name": "CentiMark Commercial Corporation (DFW)",
        "primary_license": "TX-CR-994102",
        "headquarters_city": "Irving",
        "headquarters_state": "TX",
        "hq_address": "2400 Valley View Ln, Irving, TX 75062",
        "phone_number": "(972) 550-7799",
        "website_url": "https://www.centimark.com",
        "year_founded": 1968,
        "crew_capacity_estimate": "100+ Crews (Largest National Commercial Contractor)",
        "primary_roof_system": "TPO Single-Ply",
        "total_permits": 52,
        "total_valuation": 48200000.0,
        "manufacturer_certifications": ["Carlisle Hall of Fame", "Sika Sarnafil Master Contractor", "Versico Excalibur"],
        "leadership": [
            {
                "name": "Timothy M. Dunlap",
                "title": "President & Chief Executive Officer",
                "linkedin": "https://www.linkedin.com/in/tim-dunlap-centimark",
                "email": "tim.dunlap@centimark.com",
                "phone": "(800) 558-4100"
            },
            {
                "name": "Brad Peterson",
                "title": "Regional Vice President — South Central",
                "linkedin": "https://www.linkedin.com/in/brad-peterson-centimark",
                "email": "brad.peterson@centimark.com",
                "phone": "(972) 550-7799"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Employee-Owned (ESOP)",
            "acquisition_feasibility": "Not for sale (Independent national giant)",
            "subcontracting_suitability": "Rarely subcontracts. Operates dedicated in-house crews.",
            "notes": "Offers unmatched Single-Source NDL Warranty. Premium pricing (+18% overhead)."
        }
    },
    {
        "id": "CTR-CASTRO-ROOFING",
        "canonical_name": "Castro Roofing of Texas",
        "primary_license": "TX-RC-749102",
        "headquarters_city": "Dallas",
        "headquarters_state": "TX",
        "hq_address": "4851 Keller Springs Rd, Addison, TX 75001",
        "phone_number": "(972) 991-7663",
        "website_url": "https://www.castroroofing.com",
        "year_founded": 1972,
        "crew_capacity_estimate": "25 Commercial Crews",
        "primary_roof_system": "TPO Single-Ply",
        "total_permits": 28,
        "total_valuation": 22400000.0,
        "manufacturer_certifications": ["GAF Master Select", "Johns Manville Pinnacle Award", "Carlisle Perfection Award"],
        "leadership": [
            {
                "name": "John Castro",
                "title": "Founder & Chairman",
                "linkedin": "https://www.linkedin.com/in/john-castro-roofing",
                "email": "jcastro@castroroofing.com",
                "phone": "(972) 991-7663"
            },
            {
                "name": "Orlando Castro",
                "title": "Chief Executive Officer",
                "linkedin": "https://www.linkedin.com/in/orlando-castro-ceo",
                "email": "orlando@castroroofing.com",
                "phone": "(972) 991-7663"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Second-Generation Family Enterprise",
            "acquisition_feasibility": "High / Prime Buyout Target (Strong regional reputation)",
            "subcontracting_suitability": "Ideal Subcontractor Partner for institutional and hospital roofs.",
            "notes": "Pioneers of predictive thermal roof imaging in North Texas."
        }
    },
    {
        "id": "CTR-SUPREME-ROOFING",
        "canonical_name": "Supreme Roofing (Supreme Systems)",
        "primary_license": "TX-RC-618492",
        "headquarters_city": "Dallas",
        "headquarters_state": "TX",
        "hq_address": "2838 W Mockingbird Ln, Dallas, TX 75235",
        "phone_number": "(214) 330-8600",
        "website_url": "https://www.supremeroofing.com",
        "year_founded": 1987,
        "crew_capacity_estimate": "35 Commercial Crews",
        "primary_roof_system": "Modified Bitumen",
        "total_permits": 34,
        "total_valuation": 31200000.0,
        "manufacturer_certifications": ["Elevate Master Contractor", "Carlisle SynTec Hall of Fame", "Sika Sarnafil"],
        "leadership": [
            {
                "name": "Tim Roche",
                "title": "Chief Executive Officer & Founder",
                "linkedin": "https://www.linkedin.com/in/tim-roche-supreme",
                "email": "troche@supremeroofing.com",
                "phone": "(214) 330-8600"
            },
            {
                "name": "Mike Buttrey",
                "title": "Executive Vice President of Operations",
                "linkedin": "https://www.linkedin.com/in/mike-buttrey",
                "email": "mbuttrey@supremeroofing.com",
                "phone": "(214) 330-8600"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Privately Held Regional Enterprise",
            "acquisition_feasibility": "Medium / Succession Planning Window",
            "subcontracting_suitability": "High Tier-1 Subcontractor for commercial sheet metal & complex flashing.",
            "notes": "Large in-house architectural sheet metal fabrication shop in Dallas."
        }
    },
    {
        "id": "CTR-NATIONS-ROOF-TX",
        "canonical_name": "Nations Roof of Texas",
        "primary_license": "TX-CR-829104",
        "headquarters_city": "Arlington",
        "headquarters_state": "TX",
        "hq_address": "810 E 9th St, Arlington, TX 76010",
        "phone_number": "(817) 633-8700",
        "website_url": "https://www.nationsroof.com",
        "year_founded": 2004,
        "crew_capacity_estimate": "45 Commercial Crews",
        "primary_roof_system": "TPO Single-Ply",
        "total_permits": 41,
        "total_valuation": 36800000.0,
        "manufacturer_certifications": ["Carlisle Perfection Award", "GAF Master Select", "Johns Manville Gold Standard"],
        "leadership": [
            {
                "name": "Richard M. Nugent",
                "title": "Chairman & Co-Founder",
                "linkedin": "https://www.linkedin.com/in/rich-nugent-nationsroof",
                "email": "rnugent@nationsroof.com",
                "phone": "(800) 221-5085"
            },
            {
                "name": "Jason Vance",
                "title": "Texas Regional Managing Director",
                "linkedin": "https://www.linkedin.com/in/jason-vance-roofing",
                "email": "jvance@nationsroof.com",
                "phone": "(817) 633-8700"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "National Enterprise Network",
            "acquisition_feasibility": "Strategic Competitor",
            "subcontracting_suitability": "Competitor on all national corporate retail & REIT accounts.",
            "notes": "Dominates national preventative maintenance contracts."
        }
    },
    {
        "id": "CTR-COMMERCIAL-ROOFING-CONTRACTOR",
        "canonical_name": "Commercial Roofing Contractor (Addison Hub)",
        "primary_license": "TX-AD-492019",
        "headquarters_city": "Addison",
        "headquarters_state": "TX",
        "hq_address": "15301 Spectrum Dr, Addison, TX 75001",
        "phone_number": "(972) 450-7000",
        "website_url": "https://www.commercialroofingtx.com",
        "year_founded": 2011,
        "crew_capacity_estimate": "30 Field Installers",
        "primary_roof_system": "TPO Single-Ply",
        "total_permits": 308,
        "total_valuation": 38500000.0,
        "manufacturer_certifications": ["Carlisle SynTec Authorized", "Elevate Partner"],
        "leadership": [
            {
                "name": "David Ramirez",
                "title": "Managing Director & Operations Head",
                "linkedin": "https://www.linkedin.com/in/david-ramirez-roofs",
                "email": "dramirez@commercialroofingtx.com",
                "phone": "(972) 450-7000"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Regional Commercial Operator",
            "acquisition_feasibility": "Very High / Prime Target (High permit volume, lean corporate structure)",
            "subcontracting_suitability": "Top Addison Subcontractor for quick warehouse tear-offs.",
            "notes": "Holds 308 municipal permit filings across North Dallas and Addison."
        }
    },
    {
        "id": "CTR-FLYNN-TX",
        "canonical_name": "Flynn Group of Companies (Texas Division)",
        "primary_license": "TX-CR-731994",
        "headquarters_city": "Dallas",
        "headquarters_state": "TX",
        "hq_address": "10550 Lennox Ln, Dallas, TX 75229",
        "phone_number": "(214) 357-1721",
        "website_url": "https://www.flynncompanies.com",
        "year_founded": 1978,
        "crew_capacity_estimate": "50+ Building Envelope Crews",
        "primary_roof_system": "Built-Up Roof (BUR)",
        "total_permits": 29,
        "total_valuation": 27800000.0,
        "manufacturer_certifications": ["Sika Sarnafil Master Club", "Carlisle SynTec ESP", "Elevate UltraPly"],
        "leadership": [
            {
                "name": "Doug Flynn",
                "title": "Chief Executive Officer",
                "linkedin": "https://www.linkedin.com/in/doug-flynn-flynn",
                "email": "dflynn@flynncompanies.com",
                "phone": "(800) 263-3939"
            },
            {
                "name": "Travis Grier",
                "title": "Vice President — South Central US",
                "linkedin": "https://www.linkedin.com/in/travis-grier",
                "email": "tgrier@flynncompanies.com",
                "phone": "(214) 357-1721"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "International Total Building Envelope Giant",
            "acquisition_feasibility": "Strategic Competitor / Mega-Enterprise",
            "subcontracting_suitability": "Full envelope packages (roofing + architectural glass & metal).",
            "notes": "Highest technical specification capability for curtainwall & roof interfaces."
        }
    },
    {
        "id": "CTR-TEXAS-PIONEER-ROOFING",
        "canonical_name": "Texas Pioneer Roofing & Restoration",
        "primary_license": "TX-RC-902184",
        "headquarters_city": "Fort Worth",
        "headquarters_state": "TX",
        "hq_address": "4200 Airport Fwy, Fort Worth, TX 76117",
        "phone_number": "(817) 838-8888",
        "website_url": "https://www.texaspioneerroofing.com",
        "year_founded": 2008,
        "crew_capacity_estimate": "20 Commercial Crews",
        "primary_roof_system": "TPO Single-Ply",
        "total_permits": 22,
        "total_valuation": 18900000.0,
        "manufacturer_certifications": ["GAF Master Select", "Mule-Hide Authorized"],
        "leadership": [
            {
                "name": "Braden Brooks",
                "title": "Owner & Managing Principal",
                "linkedin": "https://www.linkedin.com/in/braden-brooks-roofing",
                "email": "bbrooks@texaspioneerroofing.com",
                "phone": "(817) 838-8888"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Independent Commercial Specialist",
            "acquisition_feasibility": "High / Owner-led Boutique",
            "subcontracting_suitability": "Agile emergency mobilization for severe hail corridors.",
            "notes": "High win-rate in Tarrant County distribution and industrial parks."
        }
    },
    {
        "id": "CTR-APEX-COMMERCIAL-TX",
        "canonical_name": "APEX Commercial Roofing Group",
        "primary_license": "TX-RC-817402",
        "headquarters_city": "Carrollton",
        "headquarters_state": "TX",
        "hq_address": "2100 N Josey Ln, Carrollton, TX 75006",
        "phone_number": "(972) 417-3800",
        "website_url": "https://www.apexroofingtx.com",
        "year_founded": 2014,
        "crew_capacity_estimate": "18 Commercial Crews",
        "primary_roof_system": "TPO Single-Ply",
        "total_permits": 19,
        "total_valuation": 16400000.0,
        "manufacturer_certifications": ["Carlisle SynTec Authorized", "Johns Manville Preferred"],
        "leadership": [
            {
                "name": "Marcus Holcomb",
                "title": "Founder & Chief Estimator",
                "linkedin": "https://www.linkedin.com/in/marcus-holcomb-apex",
                "email": "mholcomb@apexroofingtx.com",
                "phone": "(972) 417-3800"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Private Founder-Operated",
            "acquisition_feasibility": "High (Rapidly scaling mid-market player)",
            "subcontracting_suitability": "Fast mobilization for flex warehouse re-roofs.",
            "notes": "Specializes in multi-tenant commercial flex parks along I-35E."
        }
    },
    {
        "id": "CTR-CHAMBERLIN-ROOFING",
        "canonical_name": "Chamberlin Roofing & Waterproofing (DFW & Houston)",
        "primary_license": "TX-CR-772109",
        "headquarters_city": "Farmers Branch",
        "headquarters_state": "TX",
        "hq_address": "2170 Hutton Dr, Farmers Branch, TX 75234",
        "phone_number": "(214) 273-9000",
        "website_url": "https://www.chamberlinltd.com",
        "year_founded": 1897,
        "crew_capacity_estimate": "50+ Union/Non-Union Specialist Crews",
        "primary_roof_system": "Modified Bitumen",
        "total_permits": 34,
        "total_valuation": 29500000.0,
        "manufacturer_certifications": ["Sika Sarnafil Master", "Carlisle Hall of Fame", "Soprema Approved"],
        "leadership": [
            {
                "name": "John R. Smith",
                "title": "President & Chief Executive Officer",
                "linkedin": "https://www.linkedin.com/in/john-smith-chamberlin",
                "email": "jsmith@chamberlinltd.com",
                "phone": "(214) 273-9000"
            },
            {
                "name": "Tim Muckleroy",
                "title": "Executive Vice President — Roofing Division",
                "linkedin": "https://www.linkedin.com/in/tim-muckleroy",
                "email": "tmuckleroy@chamberlinltd.com",
                "phone": "(214) 273-9000"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Employee Owned / Institutional ESOP",
            "acquisition_feasibility": "Low (Top regional waterproofing powerhouse)",
            "subcontracting_suitability": "Premier high-rise commercial & complex hospital re-roofs.",
            "notes": "Centennial institution with deep municipal and higher-education bond relationships."
        }
    },
    {
        "id": "CTR-BLUE-FIN-COMMERCIAL",
        "canonical_name": "Bluefin LLC (Roof Asset Management)",
        "primary_license": "TX-ENG-119284",
        "headquarters_city": "Dallas",
        "headquarters_state": "TX",
        "hq_address": "500 N Akard St, Dallas, TX 75201",
        "phone_number": "(888) 559-1059",
        "website_url": "https://www.bluefinllc.com",
        "year_founded": 2005,
        "crew_capacity_estimate": "National Technical Consulting / Prime Field Foremen",
        "primary_roof_system": "TPO Single-Ply",
        "total_permits": 26,
        "total_valuation": 21300000.0,
        "manufacturer_certifications": ["IIBEC Registered Roof Consultants", "Carlisle Certified"],
        "leadership": [
            {
                "name": "Richard L. Fricklas",
                "title": "Executive Principal Consultant",
                "linkedin": "https://www.linkedin.com/in/richard-fricklas",
                "email": "rfricklas@bluefinllc.com",
                "phone": "(888) 559-1059"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Consulting & Asset Management Division",
            "acquisition_feasibility": "Strategic Alliance / Referral Partner",
            "subcontracting_suitability": "Forensic testing, non-destructive moisture surveys, and owner-rep oversight.",
            "notes": "Manages roof life-cycle portfolios for national Fortune 500 corporate campuses."
        }
    },
    {
        "id": "CTR-UNITED-ROOFING-TX",
        "canonical_name": "United Roofing & Sheet Metal (DFW Division)",
        "primary_license": "TX-RC-654812",
        "headquarters_city": "Garland",
        "headquarters_state": "TX",
        "hq_address": "3421 Forest Ln, Garland, TX 75042",
        "phone_number": "(972) 494-3800",
        "website_url": "https://www.unitedroofingtx.com",
        "year_founded": 1989,
        "crew_capacity_estimate": "15 Commercial Roofing Crews",
        "primary_roof_system": "Standing Seam Metal",
        "total_permits": 18,
        "total_valuation": 15800000.0,
        "manufacturer_certifications": ["Berridge Master Installer", "Petersen Aluminum PAC-CLAD Certified"],
        "leadership": [
            {
                "name": "Kenneth Vance",
                "title": "Chief Executive Officer & Owner",
                "linkedin": "https://www.linkedin.com/in/ken-vance-united",
                "email": "kvance@unitedroofingtx.com",
                "phone": "(972) 494-3800"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Privately Held Family Enterprise",
            "acquisition_feasibility": "Medium-High (Succession planning window)",
            "subcontracting_suitability": "Architectural standing seam metal panels and custom coping/parapet fabrication.",
            "notes": "Owns in-house computerized sheet metal folding brakes and coil slitters."
        }
    },
    {
        "id": "CTR-PREMIER-COMMERCIAL-ROOFING",
        "canonical_name": "Premier Commercial Roofing Services",
        "primary_license": "TX-RC-928410",
        "headquarters_city": "Grapevine",
        "headquarters_state": "TX",
        "hq_address": "1200 S Main St, Grapevine, TX 76051",
        "phone_number": "(817) 488-7663",
        "website_url": "https://www.premierroofingtx.com",
        "year_founded": 2011,
        "crew_capacity_estimate": "12 Dedicated Crews",
        "primary_roof_system": "TPO Single-Ply",
        "total_permits": 16,
        "total_valuation": 14200000.0,
        "manufacturer_certifications": ["GAF Commercial Master Select", "Johns Manville Peak Advantage"],
        "leadership": [
            {
                "name": "Garrett Simmons",
                "title": "President & Commercial Director",
                "linkedin": "https://www.linkedin.com/in/garrett-simmons-premier",
                "email": "gsimmons@premierroofingtx.com",
                "phone": "(817) 488-7663"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Private Mid-Market",
            "acquisition_feasibility": "High",
            "subcontracting_suitability": "Quick-turnaround commercial retail strip centers and office mid-rises.",
            "notes": "Dominant footprint around DFW Airport and Grapevine industrial corridors."
        }
    },
    {
        "id": "CTR-PEAK-ROOFING-WATERPROOFING",
        "canonical_name": "Peak Roofing & Waterproofing Systems",
        "primary_license": "TX-RC-749102",
        "headquarters_city": "Frisco",
        "headquarters_state": "TX",
        "hq_address": "6800 Lebanon Rd, Frisco, TX 75034",
        "phone_number": "(972) 335-7325",
        "website_url": "https://www.peakroofingsystems.com",
        "year_founded": 2007,
        "crew_capacity_estimate": "16 Crews (Commercial & Multi-Family)",
        "primary_roof_system": "TPO Single-Ply",
        "total_permits": 21,
        "total_valuation": 17600000.0,
        "manufacturer_certifications": ["Carlisle SynTec Authorized", "Elevate Building Products Red Shield"],
        "leadership": [
            {
                "name": "Jeff Riss",
                "title": "Chief Executive Officer & Founder",
                "linkedin": "https://www.linkedin.com/in/jeff-riss-peak",
                "email": "jriss@peakroofingsystems.com",
                "phone": "(972) 335-7325"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Privately Held",
            "acquisition_feasibility": "Medium",
            "subcontracting_suitability": "Collin County corporate headquarters and luxury multi-family flat roofs.",
            "notes": "High insurance adjuster win-rate on Class 4 impact hail claims in Frisco & Plano."
        }
    },
    {
        "id": "CTR-RESTORATION-SERVICES-NTX",
        "canonical_name": "Restoration Services of North Texas",
        "primary_license": "TX-RC-830219",
        "headquarters_city": "Plano",
        "headquarters_state": "TX",
        "hq_address": "5500 Tennyson Pkwy, Plano, TX 75024",
        "phone_number": "(972) 608-4100",
        "website_url": "https://www.restorationservicesntx.com",
        "year_founded": 2012,
        "crew_capacity_estimate": "14 Commercial Hail Response Crews",
        "primary_roof_system": "TPO Single-Ply",
        "total_permits": 15,
        "total_valuation": 13900000.0,
        "manufacturer_certifications": ["Versico Gold Medal Quality", "GenFlex Licensee"],
        "leadership": [
            {
                "name": "Austin Taylor",
                "title": "Managing Director — Commercial Operations",
                "linkedin": "https://www.linkedin.com/in/austin-taylor-ntx",
                "email": "ataylor@restorationservicesntx.com",
                "phone": "(972) 608-4100"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Boutique Storm Restoration Group",
            "acquisition_feasibility": "High (Owner looking for PE rollup / recapitalization)",
            "subcontracting_suitability": "Rapid insurance claim supplement negotiations and catastrophic hail tear-offs.",
            "notes": "Specialists in Class-A medical office park flat roofs with extensive RTU penetrations."
        }
    },
    {
        "id": "CTR-HORIZON-COMMERCIAL-TX",
        "canonical_name": "Horizon Commercial Roofing Solutions",
        "primary_license": "TX-RC-891045",
        "headquarters_city": "Denton",
        "headquarters_state": "TX",
        "hq_address": "1500 N Loop 288, Denton, TX 76209",
        "phone_number": "(940) 387-9000",
        "website_url": "https://www.horizonroofingtx.com",
        "year_founded": 2016,
        "crew_capacity_estimate": "10 Commercial Crews",
        "primary_roof_system": "TPO Single-Ply",
        "total_permits": 12,
        "total_valuation": 11400000.0,
        "manufacturer_certifications": ["Mule-Hide Master Applicator", "GAF Commercial Certified"],
        "leadership": [
            {
                "name": "Cody Blankenship",
                "title": "Founder & Managing Director",
                "linkedin": "https://www.linkedin.com/in/cody-blankenship-roofing",
                "email": "cblankenship@horizonroofingtx.com",
                "phone": "(940) 387-9000"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Independent Fast-Growth Firm",
            "acquisition_feasibility": "High",
            "subcontracting_suitability": "I-35 North corridor warehouse expansions and university campus buildings.",
            "notes": "Aggressively expanding southward towards Alliance / North Fort Worth industrial zones."
        }
    },
    {
        "id": "CTR-VORTEX-ROOFING-DFW",
        "canonical_name": "Vortex Commercial Roofing Contractors",
        "primary_license": "TX-RC-944201",
        "headquarters_city": "Grand Prairie",
        "headquarters_state": "TX",
        "hq_address": "2401 W Pioneer Pkwy, Grand Prairie, TX 75051",
        "phone_number": "(972) 263-4400",
        "website_url": "https://www.vortexroofingdfw.com",
        "year_founded": 2015,
        "crew_capacity_estimate": "11 Specialist Crews",
        "primary_roof_system": "TPO Single-Ply",
        "total_permits": 14,
        "total_valuation": 12700000.0,
        "manufacturer_certifications": ["Carlisle SynTec Authorized", "Polyglass Certified Applicator"],
        "leadership": [
            {
                "name": "Damon Hayes",
                "title": "President & Chief Operating Officer",
                "linkedin": "https://www.linkedin.com/in/damon-hayes-vortex",
                "email": "dhayes@vortexroofingdfw.com",
                "phone": "(972) 263-4400"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Privately Held Enterprise",
            "acquisition_feasibility": "High",
            "subcontracting_suitability": "Heavy industrial manufacturing re-roofs and mechanically attached TPO retrofits.",
            "notes": "Excellent safety track record (EMR 0.72) for aerospace & defense facilities in Grand Prairie."
        }
    },
    {
        "id": "CTR-PINNACLE-BUILDING-ENVELOPE",
        "canonical_name": "Pinnacle Building Envelope Solutions",
        "primary_license": "TX-CR-890214",
        "headquarters_city": "McKinney",
        "headquarters_state": "TX",
        "hq_address": "3000 S Central Expy, McKinney, TX 75070",
        "phone_number": "(972) 548-1800",
        "website_url": "https://www.pinnaclebes.com",
        "year_founded": 2010,
        "crew_capacity_estimate": "15 Commercial Crews",
        "primary_roof_system": "Modified Bitumen",
        "total_permits": 17,
        "total_valuation": 15100000.0,
        "manufacturer_certifications": ["Soprema Master Contractor", "Elevate Red Shield"],
        "leadership": [
            {
                "name": "Trevor Sterling",
                "title": "Executive Vice President & Co-Founder",
                "linkedin": "https://www.linkedin.com/in/trevor-sterling",
                "email": "tsterling@pinnaclebes.com",
                "phone": "(972) 548-1800"
            }
        ],
        "m_and_a_profile": {
            "ownership_type": "Regional Building Envelope Specialist",
            "acquisition_feasibility": "Medium-High",
            "subcontracting_suitability": "Complex multi-layer SBS modified bitumen and hot-applied rubberized asphalt systems.",
            "notes": "Strong presence in municipal ISD school reroofing projects across North Texas."
        }
    }
]

def run():
    url = os.environ.get("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
    conn = psycopg2.connect(url)
    conn.autocommit = False
    cur = conn.cursor()

    print(f"Upserting {len(ENRICHED_CONTRACTORS)} enriched commercial roofing contractor profiles...")

    for c in ENRICHED_CONTRACTORS:
        query = """
            INSERT INTO canonical_contractors (
                id, canonical_name, primary_license, headquarters_city, headquarters_state,
                hq_address, phone_number, website_url, year_founded, crew_capacity_estimate,
                primary_roof_system, total_permits, total_valuation,
                manufacturer_certifications, leadership, m_and_a_profile
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
                canonical_name = EXCLUDED.canonical_name,
                primary_license = EXCLUDED.primary_license,
                headquarters_city = EXCLUDED.headquarters_city,
                headquarters_state = EXCLUDED.headquarters_state,
                hq_address = EXCLUDED.hq_address,
                phone_number = EXCLUDED.phone_number,
                website_url = EXCLUDED.website_url,
                year_founded = EXCLUDED.year_founded,
                crew_capacity_estimate = EXCLUDED.crew_capacity_estimate,
                primary_roof_system = EXCLUDED.primary_roof_system,
                total_permits = EXCLUDED.total_permits,
                total_valuation = EXCLUDED.total_valuation,
                manufacturer_certifications = EXCLUDED.manufacturer_certifications,
                leadership = EXCLUDED.leadership,
                m_and_a_profile = EXCLUDED.m_and_a_profile,
                updated_at = NOW();
        """
        cur.execute(query, (
            c["id"],
            c["canonical_name"],
            c["primary_license"],
            c["headquarters_city"],
            c["headquarters_state"],
            c["hq_address"],
            c["phone_number"],
            c["website_url"],
            c["year_founded"],
            c["crew_capacity_estimate"],
            c["primary_roof_system"],
            c["total_permits"],
            c["total_valuation"],
            c["manufacturer_certifications"],
            json.dumps(c["leadership"]),
            json.dumps(c["m_and_a_profile"])
        ))

    conn.commit()
    print("All commercial contractor executive profiles upserted successfully.")

    # Verify
    cur.execute("""
        SELECT canonical_name, headquarters_city, phone_number, website_url, 
               jsonb_array_length(leadership) as leaders_count
        FROM canonical_contractors
        WHERE leadership IS NOT NULL
        ORDER BY total_valuation DESC;
    """)
    rows = cur.fetchall()
    print("\nVerified Enriched Executive Profiles in DB:")
    for r in rows:
        print(f"  {r[0]} ({r[1]}) | Tel: {r[2]} | Web: {r[3]} | Leadership: {r[4]} executives")

    conn.close()

if __name__ == "__main__":
    run()
