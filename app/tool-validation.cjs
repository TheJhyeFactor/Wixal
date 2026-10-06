// Validate advertised basic schema constraints before a tool can request review or execute.
function validate(value, schema, label = 'arguments') {
 if (!schema || typeof schema !== 'object') return;
 if (schema.enum && !schema.enum.some(item=>JSON.stringify(item)===JSON.stringify(value))) throw new Error(`${label} must be one of: ${schema.enum.join(', ')}.`);
 const types=Array.isArray(schema.type)?schema.type:[schema.type];
 const matches=type=>type===undefined || type==='null'&&value===null || type==='object'&&value!==null&&typeof value==='object'&&!Array.isArray(value) || type==='array'&&Array.isArray(value) || type==='integer'&&Number.isSafeInteger(value) || type==='number'&&typeof value==='number'&&Number.isFinite(value) || type==='string'&&typeof value==='string' || type==='boolean'&&typeof value==='boolean';
 if(!types.some(matches))throw new Error(`${label} must be ${types.join(' or ')}.`);
 if(typeof value==='number'&&(schema.minimum!==undefined&&value<schema.minimum||schema.maximum!==undefined&&value>schema.maximum))throw new Error(`${label} is outside the supported range: ${schema.minimum ?? '-Infinity'} to ${schema.maximum ?? 'Infinity'}.`);
 if(typeof value==='string'&&(schema.minLength!==undefined&&value.length<schema.minLength||schema.maxLength!==undefined&&value.length>schema.maxLength))throw new Error(`${label} has an unsupported length.`);
 if(Array.isArray(value)){
  if(schema.maxItems!==undefined&&value.length>schema.maxItems)throw new Error(`${label} has too many items.`);
  for(const [i,item]of value.entries())validate(item,schema.items,`${label}[${i}]`);
 }
 if(value&&typeof value==='object'&&!Array.isArray(value)){
  for(const key of schema.required||[])if(!(key in value))throw new Error(`${label}.${key} is required.`);
  for(const [key,item]of Object.entries(value)){
   if(schema.additionalProperties===false&&!Object.hasOwn(schema.properties||{},key))throw new Error(`${label}.${key} is not a supported argument.`);
   validate(item,schema.properties?.[key],`${label}.${key}`);
  }
 }
}
module.exports={validate};
