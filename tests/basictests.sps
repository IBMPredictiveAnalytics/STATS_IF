get file="c:/spss22/samples/english/employee data.sav".
dataset name emp.

begin program.
import STATS_IF
reload(STATS_IF)
end program.

stats if condition1="True"
/syntax1 "freq jobcat." "desc salary".

stats if condition1="False"
/syntax1 "freq jobcat." "desc salary".

stats if condition1="spss.GetCaseCount() > 5" import="spss"
/syntax1 "freq jobcat." "desc salary".

* bad condition.
stats if condition1="alpha > beta" import="spss"
/syntax1 "freq jobcat." "desc salary".

* unmatched pair.

* test imports.
stats if condition1="spssaux.getShow('DIR')" import="spssaux"
/syntax1 "freq jobcat." "desc salary".

* bad syntax.  but keep going.
stats if condition1="True"
/error continue=yes print="********* Oops!"
/syntax1  "freq zz." "freq jobcat."

* atstart, atend.
stats if condition1="spss.GetCaseCount() > 5" condition2="spssaux.getShow('dir') != 'z' "
import="spssaux"
/print atstart="***** starting )BLOCK" atend="ending )BLOCK"
/error continue=yes
/syntax1 "freq jobcat"
/syntax2 "freq gender".

* do second block.
stats if condition1="spss.GetCaseCount() > 500" condition2="spssaux.getShow('dir') == r'C:\spss22' "
import="spssaux"
/print atstart="***** starting )BLOCK" atend="ending )BLOCK"
/error continue=yes print="****** Oops!"
/syntax1 "freq jobcat"
/syntax2 "freq gender".

stats if condition1="True"
/syntax1 "begin program."
"print spssaux.getShow('dir')"
"end program".

stats if.

stats if condition1="True"
/syntax1 "FREQ jobcat."
"SUMMARIZE  /TABLES=salary BY jobcat  /FORMAT=VALIDLIST NOCASENUM TOTAL LIMIT=100"
"  /TITLE='Case Summaries'  /MISSING=VARIABLE  /CELLS=COUNT MEAN MIN.".

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

* GPL blocks require special handling.
stats if condition1="True"
/syntax1
'GGRAPH'
'  /GRAPHDATASET NAME="graphdataset" VARIABLES=jobtime MISSING=LISTWISE REPORTMISSING=NO'
'  /GRAPHSPEC SOURCE=INLINE.'
'BEGIN GPL'
'  SOURCE: s=userSource(id("graphdataset"))'
'  DATA: jobtime=col(source(s), name("jobtime"))'
'  GUIDE: axis(dim(1), label("Months since Hire"))'
'  GUIDE: axis(dim(2), label("Frequency"))'
'  ELEMENT: interval(position(summary.count(bin.rect(jobtime))), shape.interior(shape.square))'
'END GPL.'
"freq jobcat.".

* MATRIX also requires special handling.
stats if condition1="True"
/syntax1
"matrix."
"compute a = {1,2,3;4,5,6}."
"print a."
"end matrix."
"freq jobcat.".
