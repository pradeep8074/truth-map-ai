import os
import pymupdf

def generate_pdf():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pdf_path = os.path.join(root_dir, "data", "demo", "kaveri_solar_proposal.pdf")
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842) # A4 size

    # Metadata
    doc.set_metadata({
        "title": "SIMULATED DEMONSTRATION DOCUMENT — Kaveri Components 100 kW Rooftop Solar Proposal",
        "author": "SunPower Industrial EPC Solutions (Fictional Vendor)",
        "subject": "Fictional Vendor Proposal for Kaveri Components Pvt Ltd",
        "creationDate": "D:20260215090000Z"
    })

    # Header Box (Simulated Watermark / Disclaimer Banner)
    header_rect = pymupdf.Rect(40, 30, 555, 75)
    page.draw_rect(header_rect, color=(0.8, 0.2, 0.2), fill=(0.98, 0.94, 0.94), width=1.5)
    page.insert_textbox(
        header_rect,
        "*** SIMULATED DEMONSTRATION DOCUMENT — FOR FORENSIC AUDIT EVALUATION ONLY ***\n"
        "FICTIONAL VENDOR PROPOSAL — CLAIMS HAVE NOT BEEN INDEPENDENTLY VERIFIED",
        fontsize=10,
        fontname="helv",
        color=(0.7, 0.1, 0.1),
        align=pymupdf.TEXT_ALIGN_CENTER
    )

    # Document Title & Parties
    meta_text = (
        "PROPOSAL REFERENCE: SEC-TN-2026-0849\n"
        "DATE: 15 February 2026\n\n"
        "CLIENT: Kaveri Components Pvt. Ltd.\n"
        "PREMISES: Plot 42, SIDCO Industrial Estate, Kurichi, Coimbatore, Tamil Nadu\n"
        "VENDOR: SunPower Industrial EPC Solutions (Simulated Commercial Entity)\n"
        "PROJECT: 100 kW Grid-Tied Captive Rooftop Solar PV Installation"
    )
    meta_rect = pymupdf.Rect(40, 85, 555, 185)
    page.insert_textbox(meta_rect, meta_text, fontsize=9.5, fontname="helv", color=(0.15, 0.15, 0.2))

    # Executive Summary & Financial Terms
    body_text = (
        "1. EXECUTIVE PROJECT SCOPE & SYSTEM CAPACITY\n"
        "SunPower Industrial EPC Solutions submits this proposal for a 100 kW grid-interactive captive rooftop solar installation at Kaveri Components Pvt. Ltd. The plant utilizes Tier-1 monocrystalline half-cut modules and string inverters.\n\n"
        "2. COMMERCIAL PRICING & PROPOSED CAPITAL COST\n"
        "• Total Turnkey Project Price: Rs. 48,00,000 (Forty-Eight Lakh Indian Rupees), inclusive of engineering, procurement, installation, and commissioning.\n\n"
        "3. GENERATION, SAVINGS & PAYBACK PROJECTIONS\n"
        "• Annual Generation Claim: 150,000 kWh (1.50 Lakh Units) annual solar generation under Tamil Nadu irradiance conditions.\n"
        "• Annual Electricity Cost Savings: Rs. 9,60,000 per year against TANGEDCO grid power tariff rate.\n"
        "• Project Payback Claim: 5 years simple payback period based on projected annual tariff avoidance.\n\n"
        "4. SUBSIDY & REGULATORY INCENTIVE CLAIMS\n"
        "• PM Surya Ghar Subsidy Claim: Vendor claims client is eligible for Rs. 78,000 capital subsidy under the PM Surya Ghar: Muft Bijli Yojana national scheme, to be deducted from initial milestone invoice.\n"
        "• TANGEDCO Export Credit Claim: Vendor claims surplus exported power will receive an export credit rate of Rs. 2.08/kWh feed-in tariff from TANGEDCO under the Tamil Nadu Unified Solar Rooftop Portal (USRP) policy.\n\n"
        "5. STATUTORY APPROVALS & ELECTRICAL SAFETY INSPECTION\n"
        "• CEIG Inspection Claim: Vendor explicitly asserts that Chief Electrical Inspector to Government (CEIG) safety inspection is Not required for this installation, claiming fast-track self-certification under standard MSME provisions.\n\n"
        "6. EQUIPMENT WARRANTY & ASSET PERFORMANCE\n"
        "• Module Warranty Claim: 25 years linear power performance warranty guaranteeing minimum 80% output at year 25.\n"
        "• Inverter Warranty: 5 years comprehensive replacement warranty.\n\n"
        "NOTICE TO AUDITOR: This is an unverified vendor commercial submission. All technical, financial, subsidy, and regulatory compliance claims must be cross-examined against prevailing TNERC regulations and official government portal mandates."
    )

    body_rect = pymupdf.Rect(40, 195, 555, 800)
    page.insert_textbox(body_rect, body_text, fontsize=9, fontname="helv", color=(0.1, 0.1, 0.1))

    doc.save(pdf_path)
    doc.close()
    print(f"Generated proposal PDF at: {pdf_path} (Size: {os.path.getsize(pdf_path)} bytes)")

if __name__ == "__main__":
    generate_pdf()
