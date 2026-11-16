import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const dir=new URL('.',import.meta.url).pathname;
const d=JSON.parse(await fs.readFile(dir+'data.json','utf8'));
const w=Workbook.create();
function sheet(name,headers,rows,widths){
 const s=w.worksheets.add(name);s.showGridLines=false;
 s.getRangeByIndexes(0,0,rows.length+1,headers.length).values=[headers,...rows];
 const all=s.getRangeByIndexes(0,0,rows.length+1,headers.length);all.format.font={name:'Arial',size:10};all.format.verticalAlignment='top';all.format.wrapText=true;
 s.getRangeByIndexes(0,0,1,headers.length).format={fill:'#243C54',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:32,wrapText:true};
 for(let c=0;c<headers.length;c++)s.getRangeByIndexes(0,c,rows.length+1,1).format.columnWidth=widths[c]??32;
 for(let r=0;r<rows.length;r++){
  const max=Math.max(...rows[r].map((v,c)=>String(v??'').length/(widths[c]??32)));
  s.getRangeByIndexes(r+1,0,1,headers.length).format.rowHeight=Math.min(160,Math.max(44,Math.ceil(max)*14+12));
  if(r%2===1)s.getRangeByIndexes(r+1,0,1,headers.length).format.fill='#F1F5F8';
 }
 s.freezePanes.freezeRows(1);s.freezePanes.freezeColumns(2);
 s.tables.add(s.getRangeByIndexes(0,0,rows.length+1,headers.length),true,name.replaceAll(' ','')+'Table');
 return s;
}
const guide=[
 ['Scope','242 provisioned fields across 16 HEW and 4 CAFE metadata blocks. All compound parents and children are included. Native citation/geospatial blocks are outside this field inventory.'],
 ['Reading direction','Metadata block and field → HEW path → Amadeus entity and slot. Paths are relative to a catalog resource unless prefixed by an annotation or related source.'],
 ['Declared HEW specification','Mapping explicitly present in mappings/amadeus/linkml_to_amadeus.yaml. This specification is not an executable adapter.'],
 ['Candidate; semantic review required','Shared slot or semantic candidate in the local schemas. Not a declared mapping or proof of compatibility. Confirm entity grain, units, enum values and cardinality.'],
 ['No declared mapping','No field-level mapping found in the HEW-owned Amadeus specification. Does not establish that Amadeus could never represent the information.'],
 ['Provisioned extension; HEW slot absent','Dataverse field exists, but the indicated property has no matching slot in the checked local HEW 2.0.0 modules. Path names document the intended extension.'],
 ['Derived/export context','Discovery projections, rollups, export versions and evidence-based CAFE indicators. These are not all direct HEW schema slots.'],
 ['Implementation boundary','Publication export implements common discovery, review, geometry and temporal mappings. Other resource types have provisioned fields and documented designs; their deposits remain separate implementation work.'],
 ['Examples','Every example is illustrative, not extracted from an observed record. Vocabulary examples use declared permissible values where available. JSON examples show shape only.'],
 ['Important transformations','Preserve timestamp offsets and exclusive interval ends. Do not convert angular resolution to metres implicitly. Preserve non-Gregorian calendars. Delivery temporal support replaces the entire dataset default.'],
 ['Vocabulary references','Controlled values contains every CAFE and HEW TSV permissible value. HEW enums lists schema enum values and meanings. Prefixes lists ontology namespaces; a namespace does not imply every field uses every ontology.'],
 ['HEW Measures','Pinned snapshot 1.0.0, source commit 632186ca971cec6fbba397620a6fa6121b37209c. Exact ontology mappings must come from a supplied mapping; no inferred equivalence.'],
 ['Snapshot date','2026-11-03; local working-tree files used.'],
 ['Dataverse repository','accel-dataverse-hew; HEAD 0f907fdd6ac8d739f7bf30c6980db5940fa9c546; assets/hew_custom.tsv, assets/cafe_custom.tsv, assets/metadata_blocks_guidance.md and crosswalks/discovery.py.'],
 ['HEW repository','HEW_Catalog_Data_Model; HEAD 8dc6ec62712bb2c6350f35c6d677564a5321f0c4; hew-model/schema/modules/*.yaml; mappings/amadeus/linkml_to_amadeus.yaml.'],
 ['Amadeus repository','amadeus_schema; HEAD 302267e8fa7f5a63b6c0c20d60cb7e2fd9c73ad1; src/amadeus_schema/schema/*.yaml, catalog version 0.1.0.'],
];
const order=[0,1,3,6,9,11,13,8,4,7,18,2,5,10,12,14,15,16,17,19,20];
const cross=sheet('Field crosswalk',['Metadata block','Dataverse field','HEW field','Amadeus field','Description','Example (illustrative)','Ontology or vocabulary','Transformation','HEW mapping basis','Amadeus mapping basis','Mapping notes','Compound parent','HEW declaring classes','HEW description','Example provenance','HEW range','Dataverse type','Multiple','Facet','Dataverse source','HEW source'],d.mapping.map(r=>order.map(i=>r[i])),[24,36,44,44,50,34,55,45,32,32,65,32,42,58,26,30,18,12,12,38,55]);
cross.tabColor='#243C54';
sheet('Amadeus specification',['HEW class','HEW path','Amadeus class','Amadeus slot','Transformation','Conditions'],d.spec,[34,48,32,46,58,100]);
sheet('Controlled values',['Dataverse field','Permissible value','Value identifier','Source'],d.cv,[44,70,45,44]);
sheet('HEW enums',['Enum','Permissible value','Ontology meaning','Description'],d.enums,[42,48,52,95]);
sheet('Prefixes',['Prefix','Namespace'],d.prefixes,[26,100]);
sheet('Read me',['Topic','Documentation'],guide,[32,110]);
w.recalculate();
console.log((await w.inspect({kind:'sheet',include:'id,name',maxChars:1500})).ndjson);
const preview=await w.render({sheetName:'Field crosswalk',range:'A40:G46',scale:1,format:'png'});
await fs.writeFile(dir+'preview.png',new Uint8Array(await preview.arrayBuffer()));
await (await SpreadsheetFile.exportXlsx(w)).save(dir+'HEW_CAFE_Amadeus_field_mapping.xlsx');
console.log('Export complete');
