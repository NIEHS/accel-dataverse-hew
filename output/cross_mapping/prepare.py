import csv,json,re,pathlib,yaml,subprocess
ROOT=pathlib.Path.cwd(); H=ROOT.parent/'HEW_Catalog_Data_Model'; A=ROOT.parent/'amadeus_schema'
slots={}; classes={}; enums={}; prefixes={}; sources={}
for p in (H/'hew-model/schema/modules').glob('*.yaml'):
 d=yaml.safe_load(p.read_text()); slots.update(d.get('slots',{})); classes.update(d.get('classes',{})); enums.update(d.get('enums',{})); prefixes.update(d.get('prefixes',{}))
 for s in d.get('slots',{}): sources[s]=str(p.relative_to(H))
am={}; ac={}
for p in (A/'src/amadeus_schema/schema').glob('*.yaml'):
 # Execution requests are outside the HEW catalog metadata scope.
 if p.stem == 'amadeus_request': continue
 d=yaml.safe_load(p.read_text()); am.update(d.get('slots',{})); ac.update(d.get('classes',{})); prefixes.update(d.get('prefixes',{}))
spec=yaml.safe_load((H/'mappings/amadeus/linkml_to_amadeus.yaml').read_text())
fields=[]; cv=[]
for filename in ['hew_custom.tsv','cafe_custom.tsv']:
 mode=''; hdr=[]
 for line,r in enumerate(csv.reader(open(ROOT/'assets'/filename),delimiter='\t'),1):
  if not r: continue
  if r[0].startswith('#'): mode=r[0]; hdr=r[1:]; continue
  if mode=='#datasetField':
   d=dict(zip(hdr,r[1:])); d['source']=f'assets/{filename}:{line}'; fields.append(d)
  if mode=='#controlledVocabulary' and len(r)>2: cv.append([r[1],r[2],r[3] if len(r)>3 else '',f'assets/{filename}:{line}'])
over={}
def group(prefix, pairs):
 for pair in pairs.split():
  k,v=pair.split('='); over[prefix+k]=v
group('hew','ResourceId=id ResourceStatus=status RelatedResource=related_resources CatalogVersion=@catalog_version SchemaVersion=@hew_schema_version CrosswalkVersion=@crosswalk_version MetadataBlockVersion=@metadata_block_version SpatialCoverage=spatial_coverage GeometryType=spatial_extent.geometry.geometry_type GeometryWkt=spatial_extent.geometry.wkt GeometryGeoJson=spatial_extent.geometry.geojson CentroidLatitude=spatial_extent.centroid.latitude CentroidLongitude=spatial_extent.centroid.longitude NamedLocation=spatial_extent.named_locations LocationIdentifier=spatial_extent.named_locations.geographic_identifiers EnvironmentalContext=spatial_extent.environmental_context EnvironmentalContextCurie=spatial_extent.environmental_context SpatialSupport=spatial_support QuantitativeSpatialResolution=quantitative_spatial_resolution AdministrativeSpatialResolution=administrative_spatial_resolution GridDefinition=grid_definition TemporalCoverage=temporal_coverage DatasetTemporalSupport=temporal_support TemporalSupport=temporal_support TemporalResolution=temporal_support.temporal_resolution TemporalCalendar=temporal_support.calendar TemporalAlignment=temporal_support.temporal_alignment DayBoundaryConvention=temporal_support.day_boundary_convention AggregationWindow=temporal_support.aggregation_window DatasetTemporalTimezone=temporal_support.timezone TemporalExtent=temporal_extent TemporalStart=temporal_extent.start_time TemporalEnd=temporal_extent.end_time TemporalTimezone=temporal_extent.timezone TemporalCoverageStatus=temporal_extent.coverage_status UpdateCadence=update_cadence_iso TypicalLatency=typical_latency_iso CoderIdentifier=annotations.coded_by ReviewerIdentifier=annotations.reviewed_by AnnotationIdentifier=annotations.id AnnotationNotes=annotations.notes DataDictionaryUrl=data_dictionary.url MeasuredVariable=measured_variables EnvironmentalVariable=environmental_variables OmopConceptId=omop_concept_binding.omop_concept_id OmopConceptStatus=omop_concept_binding.concept_status DistributionUrl=distributions.url ConceptMapping=concept_mappings VariableDefinition=variables Distribution=distributions VariableDefinitionEntry=variables DistributionEntry=distributions SurveyInstrument=survey_instruments DatasetPopulation=population')
group('hewVariable','Id=variables.id Name=variables.name Label=variables.title Description=variables.description Role=!variable_role DataType=variables.data_type Unit=variables.unit MeasuredProperty=environmental_variables.measured_property MeasurementMethod=environmental_variables.measurement_method ConceptMapping=variables.concept_mappings OmopConceptId=environmental_variables.omop_concept_binding.omop_concept_id OmopConceptStatus=environmental_variables.omop_concept_binding.concept_status')
group('hewDistribution','Id=distributions.id Title=distributions.title EntryUrl=distributions.url MediaType=distributions.media_type Format=distributions.format VariableId=distributions.variables')
group('hewSurvey','Version=version Construct=survey_constructs Question=survey_questions TargetPopulation=target_population PopulationTag=population_tags AdministeredBy=administered_by AdministrationMode=administration_mode AdministrationTime=administration_time EaseOfUse=ease_of_use ElectronicDataCapture=electronic_data_capture ReadabilityLevel=readability_level QuestionCount=question_count CdeIntegration=cde_integration AdaptedFrom=adapted_from ResearchProgram=research_program')
group('hew','AgentIdentifier=agent_associations.agent AssociatedEntity=agent_associations.associated_with AgentRole=agent_associations.role AssociationStartDate=agent_associations.start_date AssociationEndDate=agent_associations.end_date AffiliationContext=agent_associations.affiliation_context ContributionDescription=agent_associations.contribution_description ProvenanceSource=agent_associations.source SoftwareMaintainer=maintainers ModelInput=input_variables ModelOutput=output_variables ToolMaintainer=maintainers ToolInput=input_variables ToolOutput=output_variables CollectionMember=collection_members CollectionScope=collection_scope CollectionCurator=curator CollectionSourceProject=source_project CollectionVersion=version ProjectStatus=status ParentProgram=part_of_programs SponsoringOrganization=sponsoring_organizations UsesResource=uses_resources ProducesResource=produces_resources ExposureVariable=exposure_variable ExposureSourceDataset=source_dataset ExposureSourceVariable=source_variables ExposureValue=value_specification ExposurePopulation=population_or_cohort ExposureUncertainty=uncertainty ExposureQualityFlag=quality_flags CalculationMethod=method_type CalculationSoftware=software CalculationSoftwareVersion=software_version CalculationFunction=function_name CalculationParameter=parameters CalculationInput=input_resources CalculationOutput=output_variables CalculationTemporalWindow=temporal_window')
group('','workflowType=software_type workflowCodeRepository=repository workflowDocumentation=!documentation cafeDatasetTerms=@discovery_labels cafeDerivedFromExistingDataset=@derived_from_existing_dataset cafeSourceData=@source_dataset cafeSourceDataTitle=source_dataset.title cafeSourceDataAuthor=source_dataset.authors cafeSourceDataInstitution=source_dataset.source_organization cafeSourceDataVersionNumber=source_dataset.version cafeSourceDataDOIOrURL=source_dataset.identifiers cafeSourceDataLastModifiedDate=!source_last_modified cafeSourceDataDateObtained=!date_obtained cafeSourceDataType=!source_data_type cafeSourceDataTypeOther=!source_data_type_other cafeSourceDataSpatialResolution=source_dataset.quantitative_spatial_resolution cafeSourceDataSpatialValue=source_dataset.quantitative_spatial_resolution.resolution_value cafeSourceDataSpatialResolutionUnit=source_dataset.quantitative_spatial_resolution.resolution_unit cafeSourceDataSpatialResolutionUnitOther=source_dataset.quantitative_spatial_resolution.resolution_unit cafeSourceDataTimestep=source_dataset.temporal_support.temporal_resolution cafeSourceDataTimestepOther=source_dataset.temporal_support.temporal_resolution cafeSourceDataAttribution=!source_attribution cafeSourceDataDisclaimer=!source_disclaimer cafeIncludesGeospatialFile=@includes_geospatial_file cafeSpatialReferenceSystem=coordinate_reference_system_uri cafeSpatialReferenceSystemName=coordinate_reference_system cafeSpatialReferenceSystemURL=coordinate_reference_system_uri cafeSpatialFileType=spatial_extent.geometry.geometry_type cafeSpatialFileTypeOther=spatial_extent.geometry.geometry_type cafeSpatialResolution=quantitative_spatial_resolution cafeSpatialResolutionValue=quantitative_spatial_resolution.resolution_value cafeSpatialResolutionUnit=quantitative_spatial_resolution.resolution_unit cafeSpatialResolutionUnitOther=quantitative_spatial_resolution.resolution_unit')
discovery={'ResourceType':'resource_type','Exposure':'exposure_agents','HealthImpact':'health_impacts','Geography':'geographic_locations','Topic':'special_topics','Event':'event_types','DataTool':'annotations.data_tool_method_annotations.data_resource_types','Model':'annotations.data_tool_method_annotations.model_types'}
for stem,path in discovery.items():
 for suffix in ['','Concept','Curie','Alias','ExactMapping']:
  over['hew'+stem+suffix]=path
for suffix in ['Label','Curie','Alias','ExactMapping','ParentLabel','ParentCurie']: over['hewMeasure'+suffix]='@HEWM_term_lookup'
over['hewGeographicFeature']='geographic_features'
def snake(s): return re.sub(r'(?<!^)(?=[A-Z])','_',s).lower()
def owners(slot): return ', '.join(k for k,v in classes.items() if slot in v.get('slots',[]))
def target_owner(slot): return ', '.join(k for k,v in ac.items() if not k.endswith('Request') and (slot in v.get('slots',[]) or slot in v.get('attributes',{})))
vocabrows=[]
for n,e in enums.items():
 for k,v in e.get('permissible_values',{}).items(): vocabrows.append([n,str(k),(v or {}).get('meaning',''),(v or {}).get('description','')])
rows=[]
for f in fields:
 n=f['name']; path=over.get(n,snake(n.removeprefix('hew'))); leaf=path.split('.')[-1]; s=slots.get(leaf,{})
 status='Schema field'; note=''; target='No declared Amadeus mapping'; ast='No declared mapping'; operation=''
 if path.startswith('!') or leaf not in slots and not path.startswith('@'): status='Provisioned extension; HEW slot absent'; note='No matching slot in the local HEW 2.0.0 schema. Preserve source JSON; needs model alignment.'
 if path.startswith('@'): status='Derived/export context'; note='Computed or supplied by export context; not a direct HEW slot.'
 if f['metadatablock_id']=='hewReview' and not path.startswith('@'): path=path if path.startswith('annotations.') else 'annotations.'+path
 if f['metadatablock_id']=='hewDiscovery':
  note='Flatten labels separately from identifiers, aliases and exact mappings. Unknown identifiers do not become labels. Discovery hierarchy is lossy.'
  if n.startswith('hewMeasure'): note='Lookup pinned HEW Measures CURIE; collect term, aliases, exact mappings and all taxonomy ancestors except Category.'
 for cls,mp in spec['slots'].items():
  match=path
  if cls=='Distribution' and path.startswith('distributions.'): match=path[len('distributions.'):]
  elif cls!='GeospatialResource': continue
  if match in mp:
   m=mp[match]; target=spec['classes'][cls]+'.'+m['target']; ast='Declared HEW specification'; operation=m['operation']; note+=' '+m.get('notes',''); break
 if ast=='No declared mapping' and status=='Schema field' and leaf in am and leaf not in ['id','name','title','description','url','calendar','temporal_resolution','temporal_alignment','day_boundary_convention'] and f['metadatablock_id'] not in ['hewDiscovery','hewReview','hewSurvey','hewProvenance','hewProject','hewCollection']:
  own=target_owner(leaf)
  if own: target=own+'.'+leaf; ast='Candidate; semantic review required'; operation='Review entity grain and semantics before copying'
 vocab='Free text / identifier; no controlled vocabulary declared'
 rg=s.get('range','')
 if rg in enums: vocab='HEW enum: '+rg
 maps=[]
 for k in ['slot_uri','exact_mappings','close_mappings']: maps += ([s[k]] if isinstance(s.get(k),str) else s.get(k,[]))
 if maps: vocab+='; '+', '.join(maps)
 if 'Omop' in n: vocab='OMOP / OHDSI concept binding; identifiers and status must be preserved'
 if 'Curie' in n or 'ExactMapping' in n or n.startswith('hewMeasure'): vocab='HEW Measures 1.0.0 (HEWM:, vocab:); external mappings only when supplied'
 if 'Unit' in n and 'Buffer' not in n: vocab+='; UCUM preferred where supported'
 if 'CoordinateReference' in n or 'SpatialReference' in n: vocab='OGC / EPSG CRS identifier; normalize authority code for Amadeus'
 vals=[r[1] for r in cv if r[0]==n]
 if vals: vocab='CAFE local controlled vocabulary ('+str(len(vals))+' values); see Controlled values'
 ex=vals[0] if vals else ''
 if s.get('examples'): ex=str(s['examples'][0].get('value',''))
 if not ex and rg in enums: ex=str(next(iter(enums[rg].get('permissible_values',{})),''))
 if not ex:
  ex={'id':'hew:example-resource','url':'https://example.org/data','start_time':'2024-01-01T00:00:00Z','end_time':'2025-01-01T00:00:00Z','calendar':'daymet_365','aggregation_window':'P1D','unit':'Cel','coordinate_reference_system_uri':'http://www.opengis.net/def/crs/EPSG/0/4326','native_name':'tmax','resolution_value':'1000'}.get(leaf,'')
 if not ex: ex='HEWM:0000181' if 'Curie' in n else ('Drought' if 'Concept' in n or n=='hewMeasureLabel' else ('{"id":"hew:example"}' if 'JSON' in f['title'] else 'Example '+f['title'].lower()))
 rows.append([f['metadatablock_id'],n,f.get('parent',''),path.lstrip('!@'),status,owners(leaf),target,ast,operation,f['description'],s.get('description',''),ex,'Illustrative (not an observed record)',vocab,rg,f['fieldType'],f['allowmultiples'],f['facetable'],note.strip(),f['source'],('HEW_Catalog_Data_Model/'+sources[leaf]+'#slots/'+leaf) if leaf in sources else 'assets/metadata_blocks_guidance.md'])
measures=json.loads((ROOT/'accelerator_dataverse_hew/crosswalks/hew_measures_terms.json').read_text())
prefixes.update(measures['prefixes'])
out={'mapping':rows,'cv':cv,'enums':vocabrows,'prefixes':[[k,v] for k,v in prefixes.items()],'spec':[[c,p,spec['classes'][c],v['target'],v['operation'],v.get('notes','')] for c,ss in spec['slots'].items() for p,v in ss.items()]}
(ROOT/'output/cross_mapping/data.json').write_text(json.dumps(out,indent=2))
print('Fields:',len(rows),'CV values:',len(cv)); print('Extensions:',[r[1] for r in rows if r[4].startswith('Provisioned')])
