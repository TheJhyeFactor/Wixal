// Original Wixal bounded export script. The imported program is never executed.
//@category Wixal
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import com.google.gson.Gson;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

public class WixalDecompile extends GhidraScript {
    public void run() throws Exception {
        DecompInterface decompiler = new DecompInterface();
        List<Map<String,Object>> functions = new ArrayList<>();
        try {
            decompiler.openProgram(currentProgram);
            FunctionIterator iterator = currentProgram.getFunctionManager().getFunctions(true);
            int count=0;
            while(iterator.hasNext() && count++ < 32 && !monitor.isCancelled()) {
                Function function=iterator.next();
                if(function.isExternal()) continue;
                DecompileResults result=decompiler.decompileFunction(function,5,monitor);
                Map<String,Object> row=new LinkedHashMap<>();
                row.put("name",function.getName());row.put("address",function.getEntryPoint().toString());
                row.put("completed",result.decompileCompleted());
                String text=result.decompileCompleted() ? result.getDecompiledFunction().getC() : result.getErrorMessage();
                row.put("text",text.substring(0,Math.min(text.length(),16000)));functions.add(row);
            }
            Map<String,Object> output=new LinkedHashMap<>();
            output.put("language",currentProgram.getLanguageID().toString());
            output.put("compiler",currentProgram.getCompilerSpec().getCompilerSpecID().toString());
            output.put("functionCount",currentProgram.getFunctionManager().getFunctionCount());
            output.put("functions",functions);output.put("exportLimit",32);
            Files.writeString(Path.of(getScriptArgs()[0]),new Gson().toJson(output));
        } finally {decompiler.dispose();}
    }
}
