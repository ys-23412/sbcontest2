from bs4 import BeautifulSoup


def get_project_description_follow_up(html_content):
    """
    Finds the "Project Description:" label in the HTML, regardless of case or
    leading/trailing whitespace, and extracts and combines the text content
    of the next two or three siblings or HTML elements, limited to 30 words.

    Args:
        html_content (str): The HTML content as a string.

    Returns:
        str: A single string containing the combined and truncated text from
             the elements following the "Project Description:" label.
             Returns an empty string if the label is not found or no text
             can be extracted.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    project_description_label = soup.find('div', class_='sfitemFieldLbl',
                                          string=lambda text: text and "project description:" == text.strip().lower())

    if project_description_label:
        combined_text_parts = []
        current_element = project_description_label.next_sibling
        elements_found_count = 0
        
        # Iterate to grab up to 3 relevant elements
        while current_element and elements_found_count < 3:
            if current_element.name:  # Check if it's an actual HTML tag
                if current_element.name == 'br':
                    pass  # Skip <br> tags
                else:
                    combined_text_parts.append(current_element.get_text(strip=True))
                    elements_found_count += 1
            current_element = current_element.next_sibling

        # Join the extracted parts and then truncate to 30 words
        full_text = " ".join(combined_text_parts)
        words = full_text.split()
        
        if len(words) > 30:
            truncated_text = " ".join(words[:30]) + "..." # Add ellipsis for truncation
        else:
            truncated_text = " ".join(words)
            
        return truncated_text
    return "" # Return empty string if label not found

html = """
<div class="sfitemDetails">
                                <h2 id="plcContent_ctl09_ctl00_ctl00_detailContainer_mainShortTextFieldLiteral_0" class="sfitemTitle">
			IWS 2025-006 - Main No.4 Upgrade and Bear Hill Trunk Extension
		</h2>
                                <div class="sfitemPublicationDate">
			May 7, 2025, 05:14 PM
		</div>
                                <table id="SingleOpportunityTable">
                                    <tbody><tr>
                                        <td>
                                            <div class="sfitemShortTxtWrp">
                                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel1_0" class="sfitemFieldLbl">
			Project manager:
		</div>
                                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel2_0" class="sfitemShortTxt" style="display:none;">
			
		</div>
                                            </div>
                                        </td>
                                        <td>
                                            <div class="sfitemShortTxtWrp">
                                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel3_0" class="sfitemFieldLbl">
			Contact person:
		</div>
                                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel4_0" class="sfitemShortTxt">
			Shari McCreesh
		</div>
                                            </div>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>
                                            <div class="sfitemShortTxtWrp">
                                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel5_0" class="sfitemFieldLbl">
			Project manager phone:
		</div>
                                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel6_0" class="sfitemShortTxt" style="display:none;">
			
		</div>
                                            </div>
                                        </td>
                                        <td>
                                            <div class="sfitemShortTxtWrp">
                                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel7_0" class="sfitemFieldLbl">
			Contact person phone:
		</div>
                                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel8_0" class="sfitemShortTxt">
			(250) 474-9674
		</div>
                                            </div>
                                    </tr>
                                    <tr>
                                        <td>
                                            <div class="sfitemShortTxtWrp">
                                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel9_0" class="sfitemFieldLbl">
			Project ID:
		</div>
                                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel10_0" class="sfitemShortTxt">
			2025-006
		</div>
                                            </div>
                                        </td>
                                        <td>
                                            <div class="sfitemDateWrp">
                                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel11_0" class="sfitemFieldLbl">
			PublishedDate:
		</div>
                                                <div class="sfitemDate">
			May 7, 2025, 04:45 PM
		</div>
                                            </div>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>
                                            <div class="sfitemDateWrp">
                                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel12_0" class="sfitemFieldLbl">
			ClosingDate:
		</div>
                                                <div class="sfitemDate">
			Jul 16, 2025, 02:00 PM
		</div>
                                            </div>
                                        </td>
                                        <td>
                                            <div>
                                                <b>Approx. Time Left:</b><div id="countbox">15 hours, 56 minutes, 45 seconds</div>
                                            </div>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>
                                            <div class="sfitemHierarchicalTaxon sfitemTaxonWrp">
                                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel13_0" class="sfitemFieldLbl">
			Departments:
		</div>
                                                <span id="plcContent_ctl09_ctl00_ctl00_detailContainer_lblDepartments_0">Infrastructure Engineering</span>
                                        </td>
                                        <td>
                                            <div class="sfitemFlatTaxon sfitemTaxonWrp">
                                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel14_0" class="sfitemFieldLbl">
			Project Status:
		</div>
                                                <span id="plcContent_ctl09_ctl00_ctl00_detailContainer_lblProjectStatus_0">Current</span>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>
                                            <div class="sfitemFlatTaxon sfitemTaxonWrp">
                                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel15_0" class="sfitemFieldLbl">
			Tender Type:
		</div>
                                                <span id="plcContent_ctl09_ctl00_ctl00_detailContainer_lblTenderType_0">Request for Proposal</span>
                                        </td>
                                        <td></td>
                                    </tr>
                                </tbody></table>
                                <br>
                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_pnlAwardedTo_0" class="Hidden">
			
                                    <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel16_0" class="sfitemFieldLbl">
				Awarded to:
			</div>
                                    <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel17_0" class="sfitemShortTxt" style="display:none;">
				
			</div>
                                
		</div>
                                <br>
                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel18_0" class="sfitemFieldLbl">
			Project Description:
		</div>
                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel19_0" class="sfitemRichText">
			<p>May 21, 2025 - Addendum 1 Posted</p><p>May 30, 2025 - Addendum 2 Posted</p><p>June 5, 2025 - Addendum 3 Posted</p><p>June 10, 2025 - Addendum 4 Posted</p><p>June 18, 2025 - Addendum 5 Posted</p><p>June 26, 2025 - Addendum 6 Posted</p><p>July 3, 2025 - Addendum 7 Posted</p><p>July 8, 2025 - Addendum 8 Posted</p><p>July 11, 2025 - Addendum 9 Posted</p><p>_____________________________________________________________________________________________________________________________</p><p>Capital Regional District</p><p>REQUEST FOR PROPOSALS</p><p>MAIN NO.4 UPGRADE AND BEAR HILL TRUNK EXTENSION</p><p>RFP No.2025-006</p><h2>&nbsp;</h2><p><a name="_Toc197090799" data-sf-ec-immutable=""><span style="text-decoration:underline;">INTRODUCTION</span></a><span style="text-decoration:underline;"></span></p><p><a name="_Toc197090801" data-sf-ec-immutable="">Purpose of this RFP</a></p><p>The purpose of this Request for Proposals is to invite eligible Proponents to prepare and submit competitive Proposals to construct and commission the <strong>Main No. 4 Upgrade and Bear Hill Trunk Extension</strong> (the “<strong>Project</strong>”).</p><p>Through the RFP process, the CRD is seeking to enter into a construction contract (the “<strong>Construction Contract</strong>”) with an experienced, qualified contractor (the “<strong>Contractor</strong>”) to construct the Project.</p><p><a name="_Toc197090801" data-sf-ec-immutable="">Background to this RFP</a></p><p>The Capital Regional District (CRD) supplies drinking water to approximately 400,000 people within the Greater Victoria area, supporting residential, commercial, institutional, industrial, and agricultural uses via the CRD’s Regional Water Supply (RWS) and Saanich Peninsula Water (SPW) systems.</p><p>&nbsp;The RWS transmission system is generally comprised of reservoirs, dams, storage tanks, disinfection facilities, tunnels, pressure control stations, bulk meters, cathodic protection systems, and transmission main assets. There are approximately 122 kilometers of water transmission mains ranging in diameters from 400 mm to 1,525 mm and consisting of steel, ductile iron, asbestos cement, and concrete pressure pipe material.</p><p>&nbsp;The SPW system is a sub-regional CRD service that consists of transmission mains, storage tanks, pump stations, pressure control stations, and bulk meters.&nbsp; There are approximately 46 kilometers of transmission mains ranging in diameters from 200 mm to 762 mm and consisting of steel, ductile iron, PVC, asbestos cement, and fiberglass pipe material.</p><p>The CRD is seeking a qualified contractor (“Contractor”) to provide construction services associated with two (2) separate transmission main capital projects within the RWS and SPW services. The Main No. 4 Upgrade project includes the supply and installation of approximately 2910m of 762mm diameter steel pipe, including appurtenances. The Bear Hill Trunk Extension project includes the supply and installation of approximately 2925m of 600mm diameter ductile iron pipe, including appurtenances. Both projects include additional works for the District of Central Saanich and the District of North Saanich. A full description can be found in the project specifications. Prior to submitting a Proposal, Proponents should carefully review the Construction Contract. </p><p><a name="_Toc197090805" data-sf-ec-immutable="">Key Contractor Responsibilities</a></p><p>Pursuant to the Construction Contract, the Contractor will be responsible for:&nbsp; </p><p><span style="text-decoration:underline;">Main No. 4 Upgrade: </span></p><p>Supply and installation of approximately 2,916m of 762mm diameter steel pipe, including appurtenances in municipal right-of-way [CRD Asset]; </p><p>Supply and installation of approximately 725m of 200mm diameter PVC pipe and appurtenances, including bypass of existing 150mm diameter asbestos concrete water main [District of Central Saanich Asset]; and</p><p>All work required to complete the scope outlined within the Construction Contract. &nbsp;&nbsp;&nbsp;</p><p><span style="text-decoration:underline;">Bear Hill Trunk Extension: </span></p><p>Supply and installation of approximately 2,925m of 600mm diameter ductile iron pipe, including appurtenances in municipal right-of-way [CRD Asset];</p><p>Supply and installation of approximately 110m of 500mm diameter ductile iron pipe, including appurtenances in municipal right-of-way [CRD Asset]; </p><p>Supply and installation of approximately 105m of 300mm diameter ductile iron pipe, including appurtenances in municipal right-of-way [CRD Asset]; </p><p>Supply and installation of various lengths of PVC watermain, smaller than 300mm diameter, including appurtenances in municipal right-of-way [District of North Saanich and District of Central Saanich Assets];</p><p>Surface work improvements.</p><p><a name="_Toc197090817" data-sf-ec-immutable=""><span style="text-decoration:underline;">SUBMISSION INSTRUCTIONS</span></a><span style="text-decoration:underline;"></span></p><p>Closing Time and Date for Submission of Proposals</p><p>The CRD will accept <span style="text-decoration:underline;">either</span> hard copy or electronic submissions on or before the following date and time (the “<strong>Closing </strong><strong>Time”</strong>):</p><p><strong>Time:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 2:00:00 p.m. local time </strong><br><strong>Date:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; July 16, 2025</strong></p><p>The CRD reserves the right to extend the Closing Time at its sole discretion. </p><p><span style="text-decoration:underline;">Electronic Submission: </span></p><p>Submit a PDF copy of the Proposal in accordance with the instructions contained herein, to the following email address: </p><p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <strong>Email: </strong><a href="mailto:PurchasingIWS@crd.bc.ca">PurchasingIWS@crd.bc.ca</a></p><p>Delays caused by any computer related issues will not be grounds for an extension of the Closing Time. Proposals received electronically with a time stamp after the Closing Time will not be considered. CRD will utilize the timestamp on its internal e-mail system in the event of a dispute as the final time.</p><p>Submission file sizes may be larger than allowed through the CRD e-mail server.&nbsp; As an alternative, submissions can be uploaded through BC Bid’s e-Bidding.&nbsp; This option requires registering for BC Bid and instructions can be found at the following link:</p><p><a href="https://www2.gov.bc.ca/gov/content/bc-procurement-resources/bc-bid-resources/get-started-with-bc-bid/bc-bid-for-suppliers" data-sf-ec-immutable="" class="external-link" target="_blank">BC Bid for suppliers - Province of British Columbia</a></p><p><strong><span style="text-decoration:underline;">If possible, It is preferrable that submissions be received electronically through CRD’s email as noted in the tender document under Item 4 Submission Instructions, Electronic Submission.&nbsp; The maximum files size is 20 MB.</span></strong></p><p>Proposals sent by fax will not be considered. </p><p><span style="text-decoration:underline;">Hard Copy Submission: </span></p><p>Submit three (3) copies of each proposal and one (1) USB, in accordance with the instructions contained herein, at the following specific physical location: </p><p><strong>Attention: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; </strong>Shari McCreesh, Purchaser<strong></strong></p><p><strong>Address: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; </strong>Capital Regional District</p><p>&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; 479 Island Highway<br>&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; Victoria, BC&nbsp; V9B 1H7<strong><br></strong><span style="background-color:transparent;color:inherit;font-family:inherit;font-size:inherit;text-align:inherit;text-transform:inherit;word-spacing:normal;caret-color:auto;white-space:inherit;"></span></p><p><span style="background-color:transparent;color:inherit;font-family:inherit;font-size:inherit;text-align:inherit;text-transform:inherit;word-spacing:normal;caret-color:auto;white-space:inherit;">Proposals received after the Closing Time will not be considered.&nbsp; The actual time of Hard Copy Proposal submissions will be determined with reference to the clock used by the CRD for that purpose.&nbsp; Proponents are encouraged to submit their Proposals well in advance of the Closing Time to minimize the risk of their Proposal being late.</span><strong></strong></p><p>&nbsp;</p><p>&nbsp;</p><p>&nbsp;</p>
		</div>
                                <br>
                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_SitefinityLabel20_0" class="sfitemFieldLbl">
			Additional Documents:
		</div>
                                <div id="plcContent_ctl09_ctl00_ctl00_detailContainer_AdditionalDocuments_0" class="Hidden">
			
    
    
    
    
    

    
        
		</div>
                            </div>
"""

# Example usage:
result = get_project_description_follow_up(html)
print(result)