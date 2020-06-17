#/***********************************************************************
# * Licensed Materials - Property of IBM 
# *
# * IBM SPSS Products: Statistics Common
# *
# * (C) Copyright IBM Corp. 1989, 2020
# *
# * US Government Users Restricted Rights - Use, duplication or disclosure
# * restricted by GSA ADP Schedule Contract with IBM Corp. 
# ************************************************************************/


__author__  =  'IBM SPSS, JKP'
__version__ =  '1.0.1'
version = __version__

# history
# 19-May-2014 Original version

helptext = """STATS IF 
    CONDITION1="Python expression" CONDITION2="Python expression"
    ... CONDITION5="Python expression"
    IMPORTS=list of Python modules to import
/ERROR
    CONTINUE=YES or NO
    PRINT="text"
    ERRORCALL="function"
/PRINT ATSTART="text" ATEND="text"
/SYNTAX1 "SPSS code" "SPSS code" ...
/SYNTAX2 "SPSS code" ...
...
/SYNTAX5 "SPSS code"...

/HELP displays this help and does nothing else.

Example:
STATS CONDITION1="spss.GetCaseCount() > 10" CONDITION2="True"
/SYNTAX1 "FREQ x y z." "DESC a b c"
/SYNTAX2 "FREQ ALL".

At least one CONDITION and a matching SYNTAX must be specified.

CONDITION1 to CONDITION5 define up to five Python expressions.
The first one that is true (if any) causes the SYNTAX subcommand
with the matching number to be executed.  The conditions are evaluated
in numerical order, so, for example, CONDITION1, if present, is always
evaluated first.  The conditions must be quoted and follow SPSS
standard syntax quoting rules, which will be resolved before the
expression is evaluated by Python.  At most one block will be executed.
It is not an error if no block is selected.  The block numbers
present need not be consecutive.

To guarantee that at least one block is executed, you could write,
say, CONDITION5="True".

The variables in the conditions refer to Python variables, not the SPSS
data.  The variables could be defined in a previous program block or 
via apis.  For example, you could write
CONDITION1="spss.GetCaseCount() > 100"

IMPORT can specify one or more Python modules to be imported before
evaluating conditions or executing the syntax block.  The spss module
is imported automatically.

SYNTAX1...SYNTAX5 specify one or more SPSS commands to be executed.
Each line of the syntax must be enclosed in single or double quotes.
The quoting must follow SPSS standard syntax quoting rules.
BEGIN PROGRAM/END PROGRAM and BEGIN/END DATA blocks cannot be used in 
these syntax blocks.  DEFINE...!ENDDEFINE can be used, which
offers some interesting ways to combine programmability and
macro.

ERROR specifies how SPSS syntax errors affect processing.
CONTINUE=NO, which is the default, causes the syntax block
to be terminated on any error of severity 3 or higher while
CONTINUE=YES causes syntax processing to resume with the
next command in the syntax block.  Since an INSERT command
as a syntax block is a single command, CONTINUE operates
only at the level of the INSERT.

ERRORCALL can specify a Python function to be invoked when
an error occurs.  See details below.

PRINT="text" causes the text to be printed if an error occurs.

The PRINT subcommand ATSTART and ATEND keywords can specify
text to be printed at the start and end of the block selected
by the condition.

ATSTART, ATEND, and /ERROR PRINT scan the text for the string
)BLOCK and replace it with the number of the block selected
for execution.  BLOCK must be written in upper case.

More on Error Handling

An error handling function can be specified in the form
"module.function" or as "function".  If the latter, it must
have been defined in a previously executed BEGIN PROGRAM block
or be a built-in Python function.
If a module name is specified, the command will attempt to import
the function.

If an error occurs, the function will be called.  It receives four
parameters: 
the  block number (starting from 1), 
the actual command syntax where the error occurred, 
the error severity level (which is not always informative), and 
the error description.  
If the function returns the string "stop" the block is not resumed.  
If it returns "continue", processing resumes with the command 
following the error in the block being executed. 
With any other return value, including None, the action specified
in CONTINUE is taken.

Here is an example using an error handling function.
begin program.
def fixup(block, cmd, level, description):
    print "block:", block, "cmd:", cmd, "level:", level
    print "description:", description
    return "continue"
end program.

stats if condition1="True"
/error continue=no print="***** An error occurred" errorcall="fixup"
/syntax1 "freq jobcat."
"freq educ."
"freq foo."
"freq minority".

"""

from extension import Template, Syntax, processcmd
import spss
import sys, inspect

def doif(syntax1=None, condition1=None, condition2=None, condition3=None, condition4=None, condition5=None,
         syntax2=None, syntax3=None, syntax4=None, syntax5=None, importlist=None,
         errorprint=None, errorcont=False, errorcall=None, atstart=None, atend=None):
    """Execute the SPSS code in syntax blocks if corresponding condition is True"""
    # debugging
    # makes debug apply only to the current thread
    #try:
        #import wingdbstub
        #if wingdbstub.debugger != None:
            #import time
            #wingdbstub.debugger.StopDebug()
            #time.sleep(1)
            #wingdbstub.debugger.StartDebug()
        #import thread
        #wingdbstub.debugger.SetDebugThreads({thread.get_ident(): 1}, default_policy=0)
        ## for V19 use
        ###    ###SpssClient._heartBeat(False)
    #except:
        #pass
    
    if importlist:
        for m in importlist:
            exec("import %s" % m)
            ##__import__(m)
    if not errorcall is None:
        errorcall = getfunc(errorcall, 4)
            
    conditions = [condition1, condition2, condition3, condition4, condition5]
    syntaxes = [syntax1, syntax2, syntax3, syntax4, syntax5]
    pairs = [(c is not None, s is not None) for (c,s) in zip(conditions, syntaxes)]
    if any([(i+j) % 2 != 0 for (i,j) in pairs]):
        raise ValueError(_("Each condition must have a corresponding syntax block"))
    if not any([c is not None for c in conditions]):
        raise ValueError(_("""No conditions or syntax blocks were specified"""))
    for i in range(len(conditions)):
        if conditions[i] is None:
            continue
        try:
            doit = eval(conditions[i])
        except:
            raise ValueError(sys.exc_info()[1])
        if (doit) :
            doblock(i, atstart, atend, errorprint, errorcont, errorcall, syntaxes[i])
            break

    
def doblock(blocknum, atstart, atend, errorprint, errorcont, errorcall, syntax):
    """Execute block of syntax
    
    blocknum is the condition number
    atstart and atend are text to be displayed before and after
    errorprint is what to display on a syntax error
    errrcont is whether to continue running lines or stop
    syntax is a list of syntax lines to execute."""
    
    if not atstart is None:
        print(atstart.replace(")BLOCK", str(blocknum + 1)))
    lastline = len(syntax) - 1
    if lastline < 0:
        raise ValueError(_("""A syntax command block contains no syntax"""))
    
    # Submit each command one by one and handle error conditions
    cmd = []
    inmatrix = False
    for linenum, line in enumerate(syntax):
        cmd.append(line)
        # block or pseudo-block commands have to be submitted in a single call
        testline = line.rstrip().lower()
        if testline in ["matrix", "matrix."]:
            inmatrix = True        
        dosubmit = not inmatrix and (linenum == lastline or (testline.endswith(".")\
            and (syntax[linenum+1].lower().strip() not in ["begin gpl", "begin gpl."])))
        if testline == "end matrix.":
            inmatrix = False
            dosubmit = True
        if dosubmit:
            try:
                spss.Submit(cmd)
                cmd = []
            except:
                if not errorprint is None:
                    print(errorprint.replace(")BLOCK", str(blocknum + 1)))
                if not errorcall is None:
                    # an error function can take control on error.
                    # It can return "stop" or "continue" to override the action specified in STATS IF
                    action = errorcall(blocknum + 1, cmd, spss.GetLastErrorLevel(), spss.GetLastErrorMessage())
                    if action == "stop":
                        break
                    elif action == "continue":
                        cmd = []
                        continue
                if not errorcont:
                    break
                cmd = []
                
    if not atend is None:
        print(atend.replace(")BLOCK", str(blocknum + 1)))
        
def getfunc(funcname, numargs=None):
    """load and validate callability of a function.  Return the function
    
    funcname is a string that has either the form mod.func or just func"""
    
    bf = funcname.split(".")
    # try to get the function or class from the anonymous main, then check if it is a built-in
    if len(bf) == 1:
        item = bf[0].strip()
        _customfunction = getattr(sys.modules["__main__"], item, None)
        modname = "__main__"
        if _customfunction is None:
            _customfunction = __builtins__.get(item, None)
        if not callable(_customfunction):
            raise ValueError(_("""The specified function was given without a module name
    and was not found in a previous BEGIN PROGRAM block 
    and is not a built-in function: %s""") % item)
    else:
        modname = ".".join(bf[:-1])
        exec("from %s import %s as _customfunction" % (modname, bf[-1]))
    
    if not numargs is None:
        if len(inspect.getargspec(_customfunction)[0]) != numargs:
            raise ValueError(_("""The number of arguments to function %s is incorrect""") % funcname)
    return _customfunction    

def Run(args):
    """Execute the STATS IF extension command"""

    args = args[list(args.keys())[0]]

    oobj = Syntax([
        Template("CONDITION1", subc="", ktype="literal", var="condition1"),
        Template("CONDITION2", subc="", ktype="literal", var="condition2"),
        Template("CONDITION3", subc="", ktype="literal", var="condition3"),
        Template("CONDITION4", subc="", ktype="literal", var="condition4"),
        Template("CONDITION5", subc="", ktype="literal", var="condition5"),
        Template("IMPORT", subc="", ktype="literal", var="importlist", islist=True),
        
        Template("CONTINUE", subc="ERROR", ktype="bool", var="errorcont"),
        Template("PRINT", subc="ERROR", ktype="literal", var="errorprint"),
        Template("ERRORCALL", subc="ERROR", ktype="literal", var="errorcall"),
        
        Template("ATSTART", subc="PRINT", ktype="literal", var="atstart"),
        Template("ATEND", subc="PRINT", ktype="literal", var="atend"),
        
        Template("", subc="SYNTAX1", ktype="literal", var="syntax1", islist=True),
        Template("", subc="SYNTAX2", ktype="literal", var="syntax2", islist=True),
        Template("", subc="SYNTAX3", ktype="literal", var="syntax3", islist=True),
        Template("", subc="SYNTAX4", ktype="literal", var="syntax4", islist=True),
        Template("", subc="SYNTAX5", ktype="literal", var="syntax5", islist=True),
        
        Template("HELP", subc="", ktype="bool")])
    
    #enable localization
    global _
    try:
        _("---")
    except:
        def _(msg):
            return msg
    # A HELP subcommand overrides all else
    if "HELP" in args:
        #print helptext
        helper()
    else:
        processcmd(oobj, args, doif)

def helper():
    """open html help in default browser window
    
    The location is computed from the current module name"""
    
    import webbrowser, os.path
    
    path = os.path.splitext(__file__)[0]
    helpspec = "file://" + path + os.path.sep + \
         "markdown.html"
    
    # webbrowser.open seems not to work well
    browser = webbrowser.get()
    if not browser.open_new(helpspec):
        print(("Help file not found:" + helpspec))
try:    #override
    from extension import helper
except:
    pass

class NonProcPivotTable(object):
    """Accumulate an object that can be turned into a basic pivot table once a procedure state can be established"""
    
    def __init__(self, omssubtype, outlinetitle="", tabletitle="", caption="", rowdim="", coldim="", columnlabels=[],
                 procname="Messages"):
        """omssubtype is the OMS table subtype.
        caption is the table caption.
        tabletitle is the table title.
        columnlabels is a sequence of column labels.
        If columnlabels is empty, this is treated as a one-column table, and the rowlabels are used as the values with
        the label column hidden
        
        procname is the procedure name.  It must not be translated."""
        
        attributesFromDict(locals())
        self.rowlabels = []
        self.columnvalues = []
        self.rowcount = 0

    def addrow(self, rowlabel=None, cvalues=None):
        """Append a row labelled rowlabel to the table and set value(s) from cvalues.
        
        rowlabel is a label for the stub.
        cvalues is a sequence of values with the same number of values are there are columns in the table."""

        if cvalues is None:
            cvalues = []
        self.rowcount += 1
        if rowlabel is None:
            self.rowlabels.append(str(self.rowcount))
        else:
            self.rowlabels.append(rowlabel)
        self.columnvalues.extend(cvalues)
        
    def generate(self):
        """Produce the table assuming that a procedure state is now in effect if it has any rows."""
        
        privateproc = False
        if self.rowcount > 0:
            try:
                table = spss.BasePivotTable(self.tabletitle, self.omssubtype)
            except:
                spss.StartProcedure(self.procname)
                privateproc = True
                table = spss.BasePivotTable(self.tabletitle, self.omssubtype)
            if self.caption:
                table.Caption(self.caption)
            if self.columnlabels != []:
                table.SimplePivotTable(self.rowdim, self.rowlabels, self.coldim, self.columnlabels, self.columnvalues)
            else:
                table.Append(spss.Dimension.Place.row,"rowdim",hideName=True,hideLabels=True)
                table.Append(spss.Dimension.Place.column,"coldim",hideName=True,hideLabels=True)
                colcat = spss.CellText.String("Message")
                for r in self.rowlabels:
                    cellr = spss.CellText.String(r)
                    table[(cellr, colcat)] = cellr
            if privateproc:
                spss.EndProcedure()
                
def attributesFromDict(d):
    """build self attributes from a dictionary d."""
    self = d.pop('self')
    for name, value in d.items():
        setattr(self, name, value)
        
def _isseq(obj):
    """Return True if obj is a sequence, i.e., is iterable.

    Will be False if obj is a string, Unicode string, or basic data type"""

    # differs from operator.isSequenceType() in being False for a string

    if isinstance(obj, str):
        return False
    else:
        try:
            iter(obj)
        except:
            return False
        return True

