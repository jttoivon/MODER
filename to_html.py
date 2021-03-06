#!/usr/bin/python

import getopt
import sys
import re
import subprocess
import os
import numpy
import string
import math
import StringIO
import matplotlib.pyplot as plt
import matplotlib
from matplotlib import ticker
from mpl_toolkits.axes_grid1 import make_axes_locatable

css="""

h1 {
    margin-left: 100px;
}


ul {
    list-style-type: square;

}

#info {
    overflow: auto;
    background-color: lightblue;
    float: left; 
    border: solid green;
}

#programinfo {
    overflow: auto;
    background-color: lightblue;
    float: left; 
    clear: left;
    border: solid green;
    margin-top: 20px;
    margin-bottom: 20px;
    padding-right: 20px;
}

#programinfo ul {
    max-width: 60em;
}

div#lambdaTable th{
    text-align: left;
}


div#factors {
#    clear: left;
    float: left;
    text-align: center;
}
div#factors img{
#    clear: left;
#    float: left;
    padding: 20px;
}

div#flankfactors {
    clear: both;
}


#cobs {
    clear:left;
    float: left;
    text-align: center;
//    color: red;
}

div#iterations {
    float: left;
    #text-align: center;
    color: red;
}

div#iterations img{
    width: 200;
    height: 200;
}

div#background {
    overflow: auto;
    clear: left;
}

table.ppmtable th{
    background-color: lightblue;
}

table.ppmtable td,
table.ppmtable th
{
    padding: 10px;
    border: 1px solid black;
    text-align: center;
}


table.ppmtable  {
    border-collapse: collapse;
    border-spacing: 0px;
}

h3.tableheading {
    margin-top: 40px;
    margin-bottom: 10px;
}

div.rc {
    border: 2px solid white;
}
div.normal {
    border: 2px solid red;
}
div.logoContainer {vertical-align: middle;}
div.logoButtonContainer {display: inline-block; vertical-align: middle;}
div.normal { text-align: center; cursor: pointer;}
div.rc { text-align: center; cursor: pointer;}
div.logoImageContainer {display: inline-block; vertical-align: middle;}
"""


dna_orients=["HT", "HH", "TT", "TH"]
dna_orient_dict = {"HT" : 0, "HH" : 1, "TT" : 2, "TH" : 3}

rna_orients=["HT", "TH"]
rna_orient_dict = {"HT" : 0, "TH" : 1}

max_logo_width = 500 # This is defined in myspacek40

# Entropy of a probability distribution 'l'
def entropy(l):
    sum=0
    for f in l:
        if f != 0:
            try:
                sum+=f*math.log(f,2)
            except ValueError:
                print l
                raise
    return -sum;

def information_content(l):
    return 2-entropy(l)

def matrix_information_content(m):
    columns=m.transpose().tolist()  # l is list of columns
    total_ic = 0.0
    for column in columns:
        total_ic += information_content(column) 
    return total_ic


# Normalize a PFM
def normalize(m):
    for i in range(0,m.shape[1]):
        if sum(m[:,i]) != 0:
            m[:,i] /= sum(m[:,i])
    return m

def reverse_complement_pwm(m):
    result=m.copy()
    for c in range(0,m.shape[1]):
        for r in range(0,m.shape[0]):
            result[m.shape[0]-r-1,m.shape[1]-c-1] = m[r,c]
    return result

def matrices_in_orientation(o, p1, p2):
    if o == "HT":
        return (p1, p2)
    elif o == "HH":
        return (p1, reverse_complement_pwm(p2))
    elif o == "TT":
        return (reverse_complement_pwm(p1), p2)
    elif o == "TH":
        return (reverse_complement_pwm(p1), reverse_complement_pwm(p2))

def find_lines(x, str, pos, count):
    resultfile= StringIO.StringIO(string.join(x,""))
    resultlist=[]
    # read matrix header
    while True:
        line=resultfile.readline()
        if re.match(str, line):
            #line = resultfile.readline()
            if pos == 0:
                resultlist.append(line)
                count -= 1
            else:
                pos -= 1
            break
        elif line=="":
            raise AttributeError, "Tag '%s' not found" % str
    while pos > 0 and line != "":
        line = resultfile.readline()
        pos -= 1
    while count > 0:
        count -= 1
        line = resultfile.readline()
        resultlist.append(line)
    return resultlist

def readarray(lines):
    result=[]
    for line in lines:
        line = line.rstrip('\n')
        tmp=line.split("\t")
        result.append(tmp)
    return numpy.array(result)

def readmatrix(x):
    result=[]
    try:
        rows,cols=x[0].split("x")
        first=1
    except ValueError:
        first=0   # no header line
    for line in x[first:]:
        line=line.strip()
#        tmp=map(float,line.split('\t'))
        tmp=map(float,line.split())
        result.append(tmp)
    return numpy.array(result)


def compute_expected(pwm1, pwm2, o, d):
    m1,m2 = matrices_in_orientation(o, pwm1, pwm2)
    k1 = m1.shape[1]
    k2 = m2.shape[1]
    dimer_len = k1+k2+d
    fill=1.00

    # Left occurrence
    result1 = numpy.empty((4, dimer_len))
    result1.fill(fill)
    for pos in xrange(0, k1):
        result1[:,pos] = m1[:,pos]

    # Right occurrence
    result2 = numpy.empty((4, dimer_len))
    result2.fill(fill)
    for pos in xrange(k1+d, dimer_len):
        result2[:,pos] = m2[:,pos-(k1+d)]

    expected = normalize(result1 * result2)
    return expected

# Write results for a cob case
def write_results(cob, o, d, pwm1, pwm2, observed, expected, deviation, last_iteration_output, get_flanks):
    k1 = pwm1.shape[1]
    k2 = pwm2.shape[1]
    if get_flanks:
        try:
            flank=readmatrix(find_lines(last_iteration_output, "Flank dimer case matrix %s %s %i:" % (cob, o, d), 2, 4))
        except AttributeError:
            flank=numpy.zeros(expected.shape)

    oname="observed.%s.%s.%i.pfm" % (cob, o, d)
    ename="expected.%s.%s.%i.pfm" % (cob, o, d)
    dname="deviation.%s.%s.%i.dev" % (cob, o, d)
    fname="flank.%s.%s.%i.pfm" % (cob, o, d)

    writematrixfile(observed, oname)
    writematrixfile(expected, ename)
    writematrixfile(deviation, dname)
    if get_flanks:
        writematrixfile(flank, fname)



    oname_rc="observed.%s.%s.%i-rc.pfm" % (cob, o, d)
    ename_rc="expected.%s.%s.%i-rc.pfm" % (cob, o, d)
    dname_rc="deviation.%s.%s.%i-rc.dev" % (cob, o, d)
    fname_rc="flank.%s.%s.%i-rc.pfm" % (cob, o, d)

    observed_rc=reverse_complement_pwm(observed)
    expected_rc=reverse_complement_pwm(expected)
    deviation_rc=reverse_complement_pwm(deviation)
    if get_flanks:
        flank_rc=reverse_complement_pwm(flank)

    writematrixfile(observed_rc, oname_rc)
    writematrixfile(expected_rc, ename_rc)
    writematrixfile(deviation_rc, dname_rc)
    if get_flanks:
        writematrixfile(flank_rc, fname_rc)




    # Forward direction
    myrun("myspacek40 %s --logo %s %s" % (myspacek_flags, oname, oname.replace(".pfm", ".svg")))
    myrun("myspacek40 %s --logo %s %s" % (myspacek_flags, ename, ename.replace(".pfm", ".svg")))
    myrun("myspacek40 %s --difflogo %s %s" % (myspacek_flags, oname, ename))          # Deviation logo
    if get_flanks:
        if flank.shape[1] <= max_logo_width:
            myrun("myspacek40 %s -core=%i,%i,%i --logo %s %s" % (myspacek_flags, k1, k2, d, fname, fname.replace(".pfm", ".svg")))
        else:
            print "Could not create logo for flanked dimer %s %s %i: too wide logo" % (cob, o, d)
            
    # Reverse complement
    myrun("myspacek40 %s --logo %s %s" % (myspacek_flags, oname_rc, oname_rc.replace(".pfm", ".svg")))
    myrun("myspacek40 %s --logo %s %s" % (myspacek_flags, ename_rc, ename_rc.replace(".pfm", ".svg")))
    myrun("myspacek40 %s --difflogo %s %s" % (myspacek_flags, oname_rc, ename_rc))          # Deviation logo
    if get_flanks:
        if flank_rc.shape[1] <= max_logo_width:
            myrun("myspacek40 %s -core=%i,%i,%i --logo %s %s" % (myspacek_flags, k2, k1, d, fname_rc, fname_rc.replace(".pfm", ".svg")))
        else:
            print "Could not create logo for flanked dimer %s %s %i: too wide logo" % (cob, o, d)

    for rc in ["", "-rc"]:
        with open("three.%s.%s.%i%s.html" % (cob, o, d, rc), "w") as f:
            oname = "observed.%s.%s.%i%s" % (cob, o, d, rc)
            ename = "expected.%s.%s.%i%s" % (cob, o, d, rc)
            dname = "deviation.%s.%s.%i%s" % (cob, o, d, rc)
            myrun("mv %s.pfm_minus_%s.pfm.svg %s.svg" % (oname, ename, dname))
            f.write('<h1>%s %s %i</h1>' % (cob, o, d))
            f.write('<figure><figcaption>Observed:</figcaption><a href="%s.pfm"><img src="%s.svg"\></a></figure>' % (oname,oname)) 
            f.write('<figure><figcaption>Expected:</figcaption><a href="%s.pfm"><img src="%s.svg"\></a></figure>' % (ename,ename)) 
            f.write('<figure><figcaption>Deviation:</figcaption><a href="%s.dev"><img src="%s.svg"\></a></figure>' % (dname,dname)) 


    # with open("three.%s.%s.%i-rc.html" % (cob, o, d), "w") as f:
    #     oname = "observed.%s.%s.%i" % (cob, o, d)
    #     ename = "expected.%s.%s.%i" % (cob, o, d)
    #     dname = "deviation.%s.%s.%i" % (cob, o, d)
    #     myrun("mv %s-rc.pfm_minus_%s-rc.pfm.svg %s-rc.svg" % (oname, ename, dname))
    #     f.write('<h1>%s %s %i reverse complement</h1>' % (cob, o, d))
    #     f.write('<figure><figcaption>Observed:</figcaption><img src="%s-rc.svg"\></figure>' % oname) 
    #     f.write('<figure><figcaption>Expected:</figcaption><img src="%s-rc.svg"\></figure>' % ename) 
    #     f.write('<figure><figcaption>Deviation:</figcaption><img src="%s-rc.svg"\></figure>' % (dname)) 

def get_cob_case(cob, o, d, pwm1, pwm2, last_iteration_output, get_flanks):        
    expected = compute_expected(pwm1, pwm2, o, d)
    try:
        deviation=readmatrix(find_lines(last_iteration_output, "Deviation matrix %s %s %i:" % (cob, o, d), 2, 4))
    except AttributeError:
        deviation=numpy.zeros(expected.shape)
    observed = expected + deviation
    g = numpy.vectorize(lambda x : max(x,0)) # This cuts negative values to 0
    observed = normalize(g(observed)) # Because precision of (about) 6 digits is used, some elements can be slightly negative
    write_results(cob, o, d, pwm1, pwm2, observed, expected, deviation, last_iteration_output, get_flanks)
    return observed


def seconds_to_hms(seconds):
    fraction=seconds-int(seconds)
    seconds=int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    use_si_units = True
    if use_si_units:
        if h != 0:
            result = "%dh %02dm %02.2fs" % (h, m, s+fraction)
        elif m != 0:
            result = "%dm %02.2fs" % (m, s+fraction)
        else:
            result = "%.2fs" % (s+fraction)
    else:
        if h != 0:
            result = "%d:%02d:%02.2f" % (h, m, s+fraction)
        elif m != 0:
            result = "%d:%02.2f" % (m, s+fraction)
        else:
            result = "%.2f" % (s+fraction)
    return result

def extract(query, list):
    m = re.search(query, list)
    try:
        value = m.group(1)
    except:
        value = None
    return value

def extract_list(query, list):
    return re.findall(query, list)

def logo_container(anchor, image, ending, title=""):
    if len(title) > 0:
        attr='title="%s"' % title
    else:
        attr=''
    return """<div class="logoContainer">
                   <div class="logoButtonContainer">
	             <div class="normal"  onclick='myclick(event, "%s")'>+</div>
	             <div class="rc" onclick='myclick(event, "%s")'>-</div>
                   </div>
                   <div class="logoImageContainer" >
	             <a href="%s"><img class="image" src="%s" %s></a>
                   </div>
                 </div>""" % (ending, ending, anchor, image, attr)

# f ends with .svg, and is the filename of the logo
#def print_logo_container(f, logo, ending, title=""):
#    f.write(logo_container(logo.replace(".svg", ending), logo, ending, title))

def mycommand(s):
    p = subprocess.Popen(s, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (output, error) = p.communicate()
    return (p.returncode, output, error)

def make_table_h(f, files, headers, titles=[]):
    f.write("<table>")
    if len(headers) > 0:
        f.write("<tr>")
        for h in headers:
            f.write("<th>")
            f.write(h)
            f.write("</th>")
        f.write("</tr>")
    f.write("<tr>")
    if len(titles) != len(files):
        titles = [""]*len(files)
    for logo, title in zip(files, titles):
        link=logo.replace(".svg", ".pfm")
        f.write("<td>")
        f.write(logo_container(link, logo, ".pfm", title))
        f.write("</td>")
    f.write("</tr>")
    f.write("</table>")

def make_table_v(files, f, header=""):
    f.write("<table>")
    # if len(header) > 0:
    #     print "<tr>"
    #     print "<th>"
    #     print f
    #     print "</th>"
    #     print "</tr>"
    for plot in files:
        f.write("<tr>")
        f.write("<td>")
        f.write('<a href="%s"><img src="%s"\></a>' % (plot,plot))
        f.write("</td>")
        f.write("</tr>")
    f.write("</table>")

def make_table_v2(f, files, headers=[], links=[], titles=[]):
    if len(headers) != len(files):
        headers = [""]*len(files)
    if len(links) != len(files):
        links = [""]*len(files)
    if len(titles) != len(files):
        titles = [""]*len(files)
    f.write("<table>")
    for x,h,l in zip(files, headers, links):
        f.write("<tr>")
        if len(h) > 0:
            f.write("<th>%s</th>" % h)
        f.write("<td>")
        if l == "":
            l=x
        f.write('<a href="%s"><img src="%s"\></a>' % (l,x))
        f.write("</td>")
        f.write("</tr>")
    f.write("</table>")

def make_table_v3(f, files, headers, links, ending, titles=[]):
    if len(titles) != len(files):
        titles = [""]*len(files)
    f.write("<table>")
    for x,h,link, title in zip(files, headers, links, titles):
        f.write("<tr>")
        f.write("<th>%s</th>" % h)
        f.write("<td>")
        f.write(logo_container(link, x, ending, title))
#f.write('<a href="%s"><img src="%s"\></a>' % (l,f))
        f.write("</td>")
        f.write("</tr>")
    f.write("</table>")

def make_table(table, headers, f):
    f.write("<table>")
    if len(headers) > 0:
        f.write("<tr>")
        for h in headers:
            f.write("<th>")
            f.write(h)
            f.write("</th>")
        f.write("</tr>")
    for row in table:
        f.write("<tr>")
        for c in row:
            f.write("<td>")
            f.write(str(c))
            f.write("</td>")
        f.write("</tr>")
    f.write("</table>")

def make_better_table(f, table, headers=[], row_headers=[], htmlclass=""):
    if len(htmlclass) > 0:
        f.write('<table class="%s">' % htmlclass)
    else:
        f.write("<table>")
    if len(headers) > 0:
        f.write("<tr>")
        for x in headers:
            f.write("<th>%s</th>" % x)
        f.write("</tr>")
    for i, row in enumerate(table):
        f.write("<tr>")
        if len(row_headers) > 0:
            f.write("<th>%s</th>" % row_headers[i])
        for c in row:
            f.write("<td>")
            f.write(c)
            f.write("</td>")
        f.write("</tr>")
    f.write("</table>")
    

def get_best_cob_cases(cob_codes):
    best_cases=[]                                                          # ["best.observed.0-0.svg", ...]
    best_cases_links=[]                                                    # ["best.0-0.html", ...]
    best_cases_headers=[]                                                  # ["best.observed.0-0.svg", ...]
    for c in cob_codes:
        best_cases.append("best.observed.%s.svg" % c)
        best_cases_links.append("best.%s.html" % c)
        try:
            best_cases_headers.append(os.readlink("best.observed.%s.svg" % c))
        except OSError:
            best_cases_headers.append("best.observed.%s.svg(nonexisting)"%c)
    return best_cases, best_cases_links, best_cases_headers


def get_lambda_table(results_output):
    lambda_headers = factors + cobs + ["Background", "Sum"]
    # lambda_table = [ [factors[i], 0.0] for i in xrange(number_of_factors) ]  + \
    #     [ [cobs[i],   0.0]  for i in xrange(number_of_cobs) ] +\
    #     [ ["Background", 0.0], ["Sum", 0.0] ]

    bg_lambda = float(extract(r"Background lambda is (.*)", results_output))
    temp = extract(r"Fixed lambdas are (.*)", results_output) 
    monomer_lambdas = eval(temp)
    # for i,dummy in enumerate(factors):
    #     lambda_table[i][1] = monomer_lambdas[i]

    cob_lambdas = [0] * number_of_cobs
    for i, c in enumerate(cob_codes):
        cob_lambdas[i] = float(extract(r"Sum of dimer lambdas of cob table %s is (.*)" % c, results_output))

    lambdas = monomer_lambdas + cob_lambdas + [bg_lambda]
    lambda_sum = sum(lambdas)
    lambdas.append(lambda_sum)
    lambda_table2 = zip(lambda_headers, lambdas)
    
    # lambda_table[number_of_factors+number_of_cobs+1][1] = sum([float(lambda_table[i][1]) for i in xrange(0, number_of_factors + number_of_cobs + 1) ])

    # print repr(lambda_table)
    # print repr(lambda_table2)
#    assert lambda_table == lambda_table2
    
    return lambda_table2

def get_info(results_output, full_output, cob_codes):
    maxiter = int(extract(r"Maximum number of iterations is (.*)", full_output))
    iterations =  int(extract(r"EM-algorithm took (.*) = .* iterations", results_output))
    Lmin =  int(extract(r"Minimum sequence length is (.*)", full_output))
    Lmax =  int(extract(r"Maximum sequence length is (.*)", full_output))
    try:
        lines = int(extract(r"Using (.*) sequences", full_output))
    except TypeError:
        lines = int(extract(r"Read (.*) lines from file",full_output))

    command = extract(r"Command line was: (.*)", full_output)
    start_time = extract(r"Starting program at (.*)", full_output)
    version = extract(r"MODER version (.*)", full_output)
    hostname = extract(r"Running on host: (.*)", full_output)
    threads = extract(r"Using (.*) openmp threads", full_output)
    epsilon = float(extract(r"Epsilon is (.*)", full_output))
    excluded = 0
    for c in cob_codes:
        excluded += len(extract(r"Cob %s excluded cases: \[(.*)\]" % c, results_output).split(", "))
    return iterations, maxiter, Lmin, Lmax, lines, epsilon, excluded, command, start_time, version, hostname, threads


def get_seeds(full_output, number_of_factors):
    temp=extract_list(r"Fixed seeds are \[(.+)\]", full_output)
    temp2=[x.split(", ") for x in temp]
    seeds_begin = extract(r"Initial fixed seeds are \[(.+)\]", full_output).split(", ")
    #seeds_begin = ["GACCGGAAGCG", "CACCTG"]

    try:
        seeds_end=temp2[-1]
    except IndexError:
        seeds_end=seeds_begin

    with open("seeds.txt", "w") as f:
        f.write("Initial %s\n" % " ".join(seeds_begin))
        try:
            prev=temp2[0]
        except IndexError:
            pass
        for i, t in enumerate(temp2): 
            ch=[" "] * number_of_factors
            for j in xrange(number_of_factors): 
                ch[j] = str(j+1) if prev[j] != t[j] else " "
            f.write("Round %02i %s\t%s\n" % (i, " ".join(t), " ".join(ch))) # Third field contains a number for each factor that had its seed changes
                                                                            # compared to the one from the previous iteration

            prev = t
    return seeds_begin, seeds_end

# This was the old method
# def get_run_time(inputfile):
#     timefilename=re.sub("\.out", ".time", inputfile)
#     try:
#         with open(timefilename, "r") as f:
#             timedata = "".join(f.readlines())
#         runtime=extract(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): (.+)", timedata)
#     except IOError:
#         runtime="unknown"
#     return runtime

def get_run_time(results_output):
    temp=extract(r"Whole program took (.+) seconds wall-time", results_output)
    try:
        s=seconds_to_hms(float(temp))
    except TypeError:
        s="unknown"
    return s


def printmatrix(x, file=sys.stdout, headers=[], colheaders=[], format="%f", sep="\t"):
    rows, cols = x.shape
    printheaders =   len(headers) != 0
    printcolheaders =   len(colheaders) != 0
    assert(printheaders==False or len(headers) == rows) 
    if printcolheaders:
        if printheaders:
            file.write(sep)
        for j in xrange(cols-1):
            file.write("%s" % colheaders[j])
            file.write(sep)
        file.write("%s" % colheaders[cols-1])
        file.write("\n")

    for i in range(rows):
        if printheaders:
            file.write("%s%s" % (headers[i], sep))
        file.write(format % x[i,0])
        for j in xrange(1,cols):
            file.write(sep)
            file.write(format % x[i,j])
        file.write("\n")

def writematrixfile(x, filename):
    with open(filename, "w") as f:
        printmatrix(x, f)

# def mycommand(s):
#     p = subprocess.Popen(s, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     (output, error) = p.communicate()
#     return (p.returncode, output, error)

def myrun(command):
    result=os.system("%s 2>&1 > /dev/null" % command)
    if result == 0:
        print "SUCCESS %s" % command
    else:
        print "FAILURE %s" % command


def myargmax(a):
    return numpy.unravel_index(numpy.argmax(a), a.shape)


def get_monomers(factors, results_output, last_iteration_output):
    factor_lengths = [0]*len(factors)
    factor_ics = [0]*len(factors)
    factor_pwms = [0]*len(factors)
    factor_flanked_pwms = [0]*len(factors)
    
    for i, factor in enumerate(factors):
        lines=find_lines(results_output, "Fixed matrix %i:" % i, 2, 4)
#        with open("%s.pfm" % factor, "w") as f:
        with open("monomer.%i.pfm" % i, "w") as f:
            f.writelines(lines)
        factor_pwms[i] = pwm = readmatrix(lines)
        pwm_rc=reverse_complement_pwm(pwm)
#        writematrixfile(pwm_rc, "%s-rc.pfm" % factor)
        writematrixfile(pwm_rc, "monomer.%i-rc.pfm" % i)
        factor_lengths[i] = pwm.shape[1]
        factor_ics[i] = matrix_information_content(pwm)
        if get_flanks:
            lines=find_lines(last_iteration_output, "Flank fixed matrix %i:" % i, 2, 4)
            with open("flank-%i.pfm" % i, "w") as f:
                f.writelines(lines)
            flank_pwm=readmatrix(lines)
            factor_flanked_pwms[i] = flank_pwm
            flank_pwm_rc=reverse_complement_pwm(flank_pwm)
            writematrixfile(flank_pwm_rc, "flank-%i-rc.pfm" % i)
    return factor_lengths, factor_ics, factor_pwms, factor_flanked_pwms

def get_dimer_cases(results_output, iterations, last_iteration_output):
    for i, cob_factor in enumerate(cob_factors):
        number_of_orientations = 1 if use_rna else 3
        
        if cob_factor[0] != cob_factor[1]:
            number_of_orientations += 1
            
        tf1, tf2 = cob_factor
        # Find the cob table
        lines=find_lines(results_output, "Dimer lambdas %s:" % cob_codes[i], 1, number_of_orientations + 1)
        temp = readarray(lines)
        dmin[i] = int(temp[0,1])
        dmax[i] = int(temp[0,-1])
        cob_tables[i] = temp[1:,1:].astype(float)  # Remove column and row names
        #print cob_tables[i]
        cob_ic_tables[i]=numpy.zeros(cob_tables[i].shape)
        cob_length_tables[i]=numpy.zeros(cob_tables[i].shape)  # Lengths of corresponding dimeric WPM
        #print len(cob_ic_tables)
        #print cob_ic_tables[i].shape
        #overlap_table = cob_tables[i][:,0:-dmin[i]] # Only the overlap area of the cob table
        try:
            oi,di = myargmax(cob_tables[i])
            empty=False
            best_o = orients[oi]  # Maximum lambda cob case is (o,d)
            best_d = dmin[i]+di
        except ValueError:
            empty=True

        excluded=extract(r"Cob %s excluded cases: \[(.*)\]" % cob_codes[i], results_output)
        if excluded:
            excluded=excluded.split(", ")
        # for s in excluded:
        #     o2,d2 = s.split(" ")
        #     temp[1+orient_dict[o2],1+int(d2)-dmin[i]] = -0.0002   # Gets gray colour in heatmap

        # This is for the best case in this cob table
        if float(temp[1+orient_dict[best_o],1+int(best_d)-dmin[i]]) > 0.0:
            os.system("ln -f -s observed.%s.%s.%i.svg best.observed.%s.svg" % (cob_codes[i], best_o, best_d, cob_codes[i]))
            os.system("ln -f -s observed.%s.%s.%i-rc.svg best.observed.%s-rc.svg" % (cob_codes[i], best_o, best_d, cob_codes[i]))
    #        os.system("ln -f -s expected.%s.%s.%i.svg best.expected.%s.svg" % (cob_codes[i], best_o, best_d, cob_codes[i]))
    #        os.system("ln -f -s deviation.%s.%s.%i.svg best.deviation.%s.svg" % (cob_codes[i], best_o, best_d, cob_codes[i]))
            os.system("ln -f -s three.%s.%s.%s.html best.%s.html" % (cob_codes[i], best_o, best_d, cob_codes[i]))
            os.system("ln -f -s three.%s.%s.%s-rc.html best.%s-rc.html" % (cob_codes[i], best_o, best_d, cob_codes[i]))

        for row in xrange(0, number_of_orientations):
            for d in xrange(dmin[i], dmax[i]+1):
                if float(temp[1+row,1+d-dmin[i]]) > 0.00000:
                    #command="get_cob_case.py %s %i %s %s %i %s" % ("-f" if get_flanks else "", iterations-1, cob_codes[i], orients[row], d, inputfile)
                    #myrun(command)
                    dimer_pwm=get_cob_case(cob_codes[i], orients[row], d, monomer_pwms[tf1], monomer_pwms[tf2], results_output, get_flanks)
                    ic = matrix_information_content(dimer_pwm)
                    cob_ic_tables[i][row, d-dmin[i]] = ic
                    cob_length_tables[i][row, d-dmin[i]] = dimer_pwm.shape[1]
        with open("cob.%s.cob" % cob_codes[i], "w") as f:
            for row in xrange(temp.shape[0]):
                f.write("\t".join(temp[row,:]))
                f.write("\n")
        g = numpy.vectorize(lambda x,y,z : "Lambda %f&#010;IC: %f&#010;Length: %i" % (x,y,z))
        cob_titles[i] = g(cob_tables[i], cob_ic_tables[i], cob_length_tables[i])
        best_cases_titles[i]=cob_titles[i][oi, di]

def create_monomer_logos(factors, factor_lengths):
    # Monomers
    for i, f in enumerate(factors):
        #os.system("to_logo.sh -n -t %s %s.pfm" % (f, f))
#        myrun("myspacek40 -noname -paths --logo %s.pfm %s.svg" % (f, f))
#        myrun("myspacek40 -noname -paths --logo %s-rc.pfm %s-rc.svg" % (f, f))
        myrun("myspacek40 %s --logo monomer.%i.pfm monomer.%i.svg" % (myspacek_flags, i, i))
        myrun("myspacek40 %s --logo monomer.%i-rc.pfm monomer.%i-rc.svg" % (myspacek_flags, i, i))
        if get_flanks:
            g="flank-%i" % i
            if monomer_flanked_pwms[i].shape[1] <= max_logo_width:
                myrun("myspacek40 %s -core=%i --logo %s.pfm %s.svg" % (myspacek_flags, factor_lengths[i], g, g))
                myrun("myspacek40 %s -core=%i --logo %s-rc.pfm %s-rc.svg" % (myspacek_flags, factor_lengths[i], g, g))
            else:
                print "Could not create logo for flanked monomer %i: too wide logo" % i

def truncate_colormap(cmap, minval=0.0, maxval=1.0, n=100):
    new_cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        'trunc({n},{a:.2f},{b:.2f})'.format(n=cmap.name, a=minval, b=maxval),
        cmap(numpy.linspace(minval, maxval, n)))
    return new_cmap


def float_to_string(f):
    if -0.0002 <= f <= 0.0:
        return "-"
    else:
        return '%.0f' % (f*1000)
    
def make_heatmap(data, drange, title="", outputfile="", fontsize=32.0):
#    plt.style.use('ggplot')
    
    linewidth=1.0
#    fontsize=32.0
    labelfontsize=fontsize*0.6
    tickfontsize=fontsize*0.6
#    rcParams['axes.titlepad'] = 20     # Padding between the title and the plot, requires recent version of matplotlib
    
    width=data.shape[1]
    height=data.shape[0]  # number of orientations
    fig = plt.figure()
    ax = plt.subplot(111)
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
    #        plt.text(x + 0.5, y + 0.5, '%.4f' % data[y, x],
            plt.text(x, y, float_to_string(data[y, x]),
                     horizontalalignment='center',
                     verticalalignment='center',
                     )

    #plt.colorbar(heatmap)
    #cmap = matplotlib.colors.LinearSegmentedColormap.from_list("", ["red","violet","blue"])
#    white_colors = [(1, 1, 1), (1, 1, 1)]
#    white_cm = matplotlib.colors.LinearSegmentedColormap.from_list("valko", white_colors, N=256)
                    
    cmap = plt.get_cmap('YlOrRd')
    #m=np.max(data)
#    subcmap = cmap
    subcmap = truncate_colormap(cmap, 0.0, 0.8)
    subcmap.set_under(color=u'white', alpha=None)
#    constant_color = plt.cm.Blues(np.linspace(1, 1, 2))
    # stacking the 2 arrays row-wise
#    colors1 = white_cm(numpy.linspace(0, 1, 256))
#    colors2 = plt.cm.Reds(np.linspace(0, 1, 256))
#    colors2 = subcmap(numpy.linspace(0, 1, 256))
#    combined_colors = numpy.vstack((colors1, colors2))
#    combined_cmap = matplotlib.colors.LinearSegmentedColormap.from_list('colormap', combined_colors)
#    combined_cmap = truncate_colormap(combined_cmap, -0.0002, 1.0)
    plt.imshow(data, vmin=0.0, cmap=subcmap, interpolation='nearest', aspect='equal')
    divider = make_axes_locatable(ax)
    if title:
        plt.title(title, fontsize=fontsize)

    plt.yticks(fontsize=tickfontsize)
    ax.yaxis.set_ticks(numpy.arange(0,height,1))
    number_of_orientations=data.shape[0]
    ax.set_yticklabels(orients[0:number_of_orientations])
    plt.xticks(fontsize=tickfontsize)
    ax.xaxis.set_ticks(numpy.arange(0,width,1))
    ax.set_xticklabels(["%i" % i for i in drange])
    plt.tick_params(axis='both', which='both', bottom=False, top=False, right=False, left=False)

    # These lines will create grid in minor tick, that is, between cells
    ax.set_xticks(numpy.arange(-0.5, width, 1), minor=True);
    ax.set_yticks(numpy.arange(-0.5, height, 1), minor=True);
    # Gridlines based on minor ticks
    ax.grid(which='minor', color='black', linestyle='-', linewidth=1)

    cax = divider.append_axes("right", size="5%", pad=0.05)
    try:
        cb=plt.colorbar(cax=cax)
        tick_locator = ticker.MaxNLocator(nbins=5)
        cb.locator = tick_locator
        ##cb.ax.yaxis.set_major_locator(matplotlib.ticker.AutoLocator())                                             
        cb.update_ticks()
        temp=cax.get_yticklabels()
        for i,t in enumerate(temp):
            #print temp[i].get_text()
#            temp[i].set_text("%.0f" % (float(temp[i].get_text())*1000))   # Multiply values in colorbar by 1000
            temp[i] = "%.0f" % (float(temp[i].get_text())*1000)   # Multiply values in colorbar by 1000
        cax.set_yticklabels(temp, fontsize=tickfontsize)
    except UnicodeEncodeError:   # If labels contain unicode minus, then something went wrong and better not show colorbar
        cb.remove()
        pass
#    cax.yaxis.set_tick_params(labelright=False)   # No tick labels in colorbar
    if outputfile:
        plt.savefig(outputfile, format="svg", bbox_inches="tight")
    else:
        pass#plt.show()

            
def visualize_cobs(cobs, cob_codes):            
    for i, (cob, code) in enumerate(zip(cobs, cob_codes)):
        f = "cob.%s" % code
        #    myrun('heatmap.R -z 8 -c -s -f "%%.3f" -t %s %s.cob' % (f, f))
        data=cob_tables[i]
        vfunc = numpy.vectorize(lambda x: x if x > 0.0 else -0.0002)
        data=vfunc(data)
        drange = range(dmin[i], dmax[i]+1)
        print "Creating heatmap for %s" % cob
        make_heatmap(data, drange, cob, "%s.svg" % f, fontsize=20.0)
#        myrun('heatmap.R -z 12 -c -s -i -t %s %s.cob 2> /dev/null > /dev/null' % (cob, f))
#        myrun("sed -i '/page/d' %s.svg" % f)  # R or its pheatmap package make svg files corrupt. This fixes it.
    #    myrun('heatmap.R -z 8 -c -s -f "%%.3f" -t %s %s.cob' % (f, f))


###################################################################################
#
#  Create distance, information content, lambda, log likelihood and parameter plots
#
###################################################################################

def myplot(data, title="", xlab="", ylab="", ymax=None, headers=[], outputfile=""):
    linewidth=2.0
    fontsize=32.0
    labelfontsize=fontsize*0.6
    tickfontsize=fontsize*0.6
    fig = plt.figure()
    ax = plt.subplot(111)
    if title:
        plt.title(title, fontsize=fontsize, fontname='sans-serif')
#    if ylab=="mll":
#        plt.ylabel(ylab, fontsize=labelfontsize, labelpad=20)
#    else:
    plt.ylabel(ylab, fontsize=labelfontsize)
    plt.xlabel(xlab, fontsize=labelfontsize)
    plt.xticks(fontsize=tickfontsize)
    plt.yticks(fontsize=tickfontsize)
    if not ymax is None:
        a = ymax*0.05            # Add margin to y-axis
        plt.ylim(0.0-a, ymax+a)
    ax.plot(data, linewidth=linewidth)
    ax.margins(x=0.05)           # Add margin to x-axis
    plt.grid(True)
    if headers:
        # Shrink current axis by 30%
        box = ax.get_position()
        if ylab=="mll":           # Make some more room for ylabel because of longer ytick labels
            ax.set_position([box.x0+0.10*box.width, box.y0, box.width * 0.7, box.height])
        else:
            ax.set_position([box.x0, box.y0, box.width * 0.7, box.height])
        # Put a legend to the right of the current axis
        plt.legend(headers, title="Models", loc='center left', bbox_to_anchor=(1, 0.5))
    if outputfile:
        plt.savefig(outputfile, format="svg")
    else:
        plt.show()

def create_graphs(full_output, factors, cobs, cob_codes):
    temp=extract_list(r"Log likelihood is (.+)", full_output)
    mll_header=["Log likelihood"]
    mll_data=[]
    with open("mll.txt", "w") as f:
        f.write("%s\n" % ("\t".join(mll_header)))
        for t in temp:
            mll_data.append(t)
            f.write("%s\n" % t)

    temp=extract_list(r"Total number of parameters is (.+)", full_output)
    parameters_header=["Number of parameters"]
    parameters_data=[]
    with open("parameters.txt", "w") as f:
        f.write("%s\n" % ("\t".join(parameters_header)))
        for t in temp:
            parameters_data.append(t)
            f.write("%s\n" % t)

    temp=extract_list(r"Intermediate average information content of fixed models: \[(.+)\]", full_output)
    ics_header=factors
    ics_data=[]
    with open("ics.txt", "w") as f:
        f.write("%s\n" % ("\t".join(ics_header)))
        for t2 in temp:
            t = t2.split(", ")
            ics_data.append(t)
            f.write("%s\n" % "\t".join(t))

    distances_header=factors+cobs
    distances_data=[]
    with open("distances.txt", "w") as f:
        cols=len(factors+cobs)
        temp=extract_list(r"Fixed distances are \[(.+)\]", full_output)
        rows=len(temp)
        a=numpy.empty((rows,cols))
        for r,t in enumerate(temp):
            for c,x in enumerate(t.split(", ")):
                a[r,c]=float(x)
        for c, cob in enumerate(cob_codes):
            query=r"Max distance in deviation %s is (.+)" % cob
            #print query
            temp=extract_list(query, full_output)
            #print temp
            for r,t in enumerate(temp):
                a[r,len(factors)+c] = float(t)
        f.write("%s\n" % ("\t".join(distances_header)))
        #printmatrix(a, sys.stdout, headers=[], colheaders=[], format="%f", sep="\t")
        printmatrix(a, f, headers=[], colheaders=[], format="%f", sep="\t")
        distances_data = a.tolist()

    lambdas_header=factors+cobs+["bg"]
    lambdas_data=[]
    with open("lambdas.txt", "w") as f:
        temp=extract_list(r"Intermediate fixed lambdas are \[(.+)\]", full_output)
        atemp=[t.split(", ") for t in temp]
        #print atemp
        a=numpy.array(atemp)
        btemp=[]
        for cob in cob_codes:
            #print "Cob is %s" % cob
            temp=extract_list(r"Intermediate sum of dimer lambdas %s is (.+)" % cob, full_output)
            btemp.append(temp)
    #    print btemp
        b=numpy.transpose(numpy.array(btemp))
        temp=extract_list(r"Intermediate background lambda is (.+)", full_output)
        c=numpy.transpose(numpy.array([temp]))
        f.write("%s\n" % ("\t".join(lambdas_header)))

        if len(cob_codes) > 0:
            d=numpy.concatenate((a,b,c), 1)
        else:
            d=numpy.concatenate((a,c), 1)
        #printmatrix(d, format="%s")
        printmatrix(d, f, headers=[], colheaders=[], format="%s", sep="\t")
        lambdas_data=d.tolist()

    myplot(mll_data, "%s log likelihood" % name, "iterations", "mll", headers=lambdas_header, outputfile="mll.svg")
    myplot(parameters_data, "%s number of parameters" % name, "iterations", "params", headers=parameters_header, outputfile="parameters.svg")
    myplot(ics_data, "%s information content" % name, "iterations", "IC", ymax=2.0, headers=ics_header, outputfile="ics.svg")
    myplot(distances_data, "%s convergence" % name, "iterations", "distance", ymax=1.0, headers=distances_header, outputfile="distances.svg")
    myplot(lambdas_data, "%s lambdas" % name, "iterations", "lambda", ymax=1.0, headers=lambdas_header, outputfile="lambdas.svg")

    # myrun('plot.R -c -s -x iterations -y mll -t "%s log likelihood" mll.txt' % name)
    # myrun('plot.R -c -s -x iterations -y params -t "%s number of parameters" parameters.txt' % name)
    # myrun('plot.R -c -s -b 2.0 -x iterations -y IC -t "%s information content" ics.txt' % name)
    # myrun('plot.R -c -s -b 1.0 -h 0.01 -x iterations -y distance -t "%s distances" distances.txt' % name)
    # myrun('plot.R -c -s -b 1.0 -x iterations -y lambda -t "%s lambdas" lambdas.txt' % name)





# This is to locate helper scripts in the same directory as this file
execdir=os.path.abspath(os.path.dirname(sys.argv[0]))
#print "execdir is %s" % execdir
path=os.getenv("PATH")
os.putenv("PATH", path+":"+execdir)

usage="""Usage:
\tto_html.py tf1name,tf2name,... moderoutputfile

Parses the output created by MODER and converts it to a graphical
html page. The first parameter is a comma separated list
of factor names. The second parameter is the name of the
MODER output file.

A directory 'moderoutputfile.report' is created, and
the report will be in file 'moderoutputfile.report/index.html'
"""

try:
    optlist, args = getopt.getopt(sys.argv[1:], 'hd', ["help", "debug"])
except getopt.GetoptError as e:
    print e
    sys.stderr.write(usage)
    sys.exit(1)
    
optdict = dict(optlist)
args = [sys.argv[0]]+ args
debug=False

#print optdict
for o, a in optlist:
        if o in ("-h", "--help"):
            print usage
            sys.exit(0)
        elif o in ("-d", "--debug"):
            debug=True
            print "Debugging on"
        else:
            sys.stderr.write("Unknown option: %s\n" % o)
            sys.stderr.write(usage)
            sys.exit(1)
            


if len(args) == 1:
    print usage
    sys.exit(0)
elif len(args) != 3:
    sys.stderr.write("Error, give two parameters.\n")
    sys.stderr.write(usage)
    sys.exit(1)

name=args[1]
orig=inputfile=args[2]

if inputfile[1:].count(".") > 0:                         # Contains a file extension
    mydir=re.sub("\.[^.]*?$", ".report", inputfile)
else:
    mydir="%s.report" % inputfile
reportfile="%s/index.html" % mydir

inputfile = "../%s" % os.path.basename(inputfile)

try:
    os.mkdir(mydir)
except OSError:
    pass

os.chdir(mydir)

factors=name.split(',')  # For example ['FLI1a', 'FLI1b']

try:
    with open(inputfile) as f:
        full_output = "".join(f.readlines())
except IOError:
    sys.stderr.write("Could not read file %s. Exiting!\n" % orig)
    sys.exit(1)
                     

use_rna = extract(r"Use RNA alphabet: (.*)", full_output)
if use_rna == "yes":
    use_rna = True
    orients = rna_orients
    orient_dict = rna_orient_dict
    myspacek_flags="-paths -noname -rna"
else:
    use_rna = False
    orients = dna_orients
    orient_dict = dna_orient_dict
    myspacek_flags="-paths -noname"
    
cob_factors=extract(r"Cob combinations are ([0-9,-]*)", full_output)
if cob_factors:
    cob_factors=cob_factors.split(",")
else:
    cob_factors=[]
cob_factors=[map(int, x.split("-")) for x in cob_factors]              # cob_factors=[[0,0], [1,1], [0,1]]
number_of_cobs=len(cob_factors)
factor_codes=set()
for x,y in cob_factors:
    factor_codes.add(x)
    factor_codes.add(y)
# In the if clause below, if only one name e.g. HNF4A is given and four codes 0,1,2,3 are used in cob types, then form names
# HNF4Aa,HNF4Ab,HNF4Ac,HNF4Ad
if len(factors) == 1 and len(factor_codes) > 1:
    new_factors=[factors[0]+chr(ord('a')+x) for x in xrange(max(factor_codes)+1) ]
    factors = new_factors

number_of_factors=len(factors)



cobs=['-'.join([factors[x[0]], factors[x[1]]]) for x in cob_factors ]  # cobs=["TEAD4-TEAD4", "ERG-ERG",  "TEAD4-ERG"]
cob_codes=[ "-".join(map(str,x)) for x in cob_factors ]                # cob_codes=["0-0", "1-1", "0-1"]


command="sed -n '/Results/,$p' %s" % inputfile
(ret_val, results_output, error) = mycommand(command)
assert ret_val == 0


######################################################################################################
#
# to_logos
#


cob_tables=[0]*number_of_cobs
cob_ic_tables=[0]*number_of_cobs
cob_length_tables=[0]*number_of_cobs
cob_titles=[0]*number_of_cobs
dmin=[0]*number_of_cobs
dmax=[0]*number_of_cobs

get_flanks = extract(r"Get full flanks: (.*)", full_output) == "yes"

iterations =  int(extract(r"EM-algorithm took (.*) = .* iterations", results_output))

command="sed -n '/Round %i/,/^-+$/p' %s" % (iterations-1,inputfile)   # Output from last iteration onwards
(ret_val, last_iteration_output, error) = mycommand(command)

monomer_lengths, monomer_ics, monomer_pwms, monomer_flanked_pwms = get_monomers(factors, results_output, last_iteration_output)

best_cases_titles=[0]*number_of_cobs
get_dimer_cases(results_output, iterations, last_iteration_output)
create_monomer_logos(factors, monomer_lengths)
visualize_cobs(cobs, cob_codes)
if debug:
    create_graphs(full_output, factors, cobs, cob_codes)

# temp=extract_list(r"Background distribution \(intermed\): \[(.+)\]", full_output)
# bg=[x.split(", ") for x in temp]
# with open("background.txt", "w") as f:
#     bg_t=numpy.array(bg).transpose()
#     for t in bg_t: 
#         f.write("%s\n" % ("\t".join(t)))
# myrun('myspacek40 --logo -paths background.txt background.svg')



######################################################################################################
#
# Print html
#



#logo_files = [ s+".svg" for s in factors ]                             # logo_files=["TEAD4.svg", "ERG.svg"]
logo_files = [ "monomer.%i.svg" % i for i in xrange(number_of_factors) ]   # logo_files=["monomer.0.svg", "monomer.1.svg"]
#cob_files = [ s+".svg" for s in cobs ]                                 # cob_files=["TEAD4-TEAD4.svg", "ERG-ERG.svg",  "TEAD4-ERG.svg"]
cob_files = [ "cob.%s.svg" % s for s in cob_codes ]                       # cob_files=["cob.0-0.svg", "cob.1-1.svg",  "cob.0-1.svg"]
cob_links = [ "cob.%s.array.html" % s for s in cob_codes ]             # ["cob.0-0.array.html", "cob.1-1.array.html", ... ]


best_cases, best_cases_links, best_cases_headers = get_best_cob_cases(cob_codes)

lambda_table = get_lambda_table(results_output)



iterations, maxiter, Lmin, Lmax, lines, epsilon, excluded, command, start_time, version, hostname, threads = get_info(results_output, full_output, cob_codes)

#Background distribution: [0.30201, 0.294127, 0.202849, 0.201013]
bg_dist = map(float, extract(r"Background distribution: \[(.*)\]", results_output).split(', '))

seeds_begin, seeds_end = get_seeds(full_output, number_of_factors)

def get_monomer_modularity(full_output):
    temp=extract_list(r"Is monomer pwm learnt purely modularly: \[(.+)\]", full_output)
    temp2=[x.split(", ") for x in temp]
    return temp2[-1]

monomer_modularity = get_monomer_modularity(full_output)


runtime = get_run_time(results_output)

    


f = open('index.html', 'w')
    
f.write("<html>\n")

f.write("<head>\n")
javascript='''
  <script type="text/javascript">
    function myclick(e, ending)
    {
    t=e.target;
    t.style.borderColor="red";
    logo_container = t.parentNode.parentNode;
    image_node = logo_container.getElementsByClassName("image")[0];
    anchor_node = logo_container.getElementsByTagName("a")[0];
    if (t.className=="normal") {
      var other=logo_container.getElementsByClassName("rc")[0];
      image_node.src = image_node.src.replace("-rc.svg", ".svg");
      anchor_node.href= anchor_node.href.replace("-rc".concat(ending), ending);
    } else {
      var other=logo_container.getElementsByClassName("normal")[0];
      if (! image_node.src.endsWith("-rc.svg")) {
        image_node.src= image_node.src.replace(".svg", "-rc.svg");
        anchor_node.href= anchor_node.href.replace(ending, "-rc".concat(ending));
      }
    }
    other.style.borderColor="white";
    }
  </script>
'''
f.write(javascript)

f.write('<link rel="stylesheet" href="style.css" type="text/css" />\n')
f.write("<title>%s - %s</title>\n" % (name, re.sub("^../", "", inputfile)))

f.write("</head>\n")

f.write("<body>\n")

f.write("<h1>MODER - MOtif DEtectoR</h1>\n")
f.write("<h2>%s - %s</h2>\n" % (name, re.sub("^../", "", inputfile)))


###################
#
# Print the infobox

f.write('<div id="info">\n')

f.write('<div style="float: left; padding: 20px;">\n')
f.write("<ul>\n")
#print """<li>Result file: <a href="%s" onclick="window.open('%s', 'newwindow', 'width=300, height=250'); return false;">%s</a></li>""" % (inputfile, inputfile, inputfile)
f.write("""<li>Result file: <a href="%s">%s</a></li>""" % (inputfile, re.sub("^../", "", inputfile)))

if Lmin == Lmax:
    L="%s" % Lmin
else:
    L="%s-%s" % (Lmin, Lmax)
f.write("<li>Data contains %i sequences of length %s </li>" % (lines, L))
f.write("<li>Running time was (wall-clock) %s</li>" % runtime)
if iterations == maxiter:
    f.write("<li>EM-algorithm took <span style='color: red;'>%i iterations</span> (max-iter=%i)</li>" % (iterations, maxiter))
else:
    f.write("<li>EM-algorithm took %i iterations (max-iter=%i)</li>" % (iterations, maxiter))
f.write("<li>Convergence criterion cutoff is %g</li>" % epsilon)
f.write("<li>Excluded cob cases: %i</li>" % excluded)
f.write("<li>Are monomers learnt modularly: %s</li>" % " ".join(monomer_modularity))
f.write('<li>Initial and final <a href="seeds.txt">consensus sequences</a> of lengths %s:</li>' % (" ".join(map(lambda x : str(len(x)), seeds_begin))))
f.write("<ul>")
f.write('<li style="font-family: monospace;">%s</s>' % (" ".join(seeds_begin)))
f.write('<li style="font-family: monospace;">%s</s>' % (" ".join(seeds_end)))
f.write("</ul>")
f.write("<li>Bg: %s</li>" % (" ".join(["%.2f" % x for x in bg_dist])))
f.write("</ul>")
f.write("</div>\n")
f.write('<div id="lambdaTable" style="float: left; padding: 20px;">\n')
make_table(lambda_table, ["Model", "Lambda"], f)
f.write("</div>\n")
f.write("</div>\n")


###################
#
# Print the factors

monomer_lambdas=[ y for x,y in lambda_table][0:number_of_factors]
# These are for the title attribute of the images
monomer_titles=[ "Lambda: %f&#010;IC: %.2f&#010;Length: %i" % (l,i, length) for l, i, length in zip(monomer_lambdas, monomer_ics, monomer_lengths)]
f.write('<div id="factors">')
f.write('<h2>Monomer motifs</h2>')
make_table_h(f, logo_files, factors, monomer_titles)
f.write("</div>")


###################
#
# Print the cob tables and the best case from each cob table

if number_of_cobs > 0:
    f.write('<div id="cobs">')
    f.write('<h2>COB tables</h2>')
    make_table_v2(f, cob_files, [""]*number_of_cobs, cob_links)
    f.write('<h2>Strongest dimeric case from each cob table</h2>')
    make_table_v3(f, best_cases, best_cases_headers, best_cases_links, ".html", best_cases_titles)
    f.write("</div>")

###############################
#
# Print the factors with flanks

if get_flanks:
    f.write('<div id="flankfactors">')
    f.write('<h2>Monomer motifs with flanks</h2>')
    flank_logo_files=["flank-%i.svg" % i for i in xrange(number_of_factors)]
    make_table_v3(f, flank_logo_files, factors, [x.replace(".svg", ".pfm") for x in flank_logo_files], ".pfm", monomer_titles)
    f.write("</div>")

###################
#
# Print behaviour as function of iterations

if debug:
    f.write('<div id="iterations">')
    #(files, headers=[], links=[], f, titles=[])
    make_table_v(["distances.svg", "ics.svg", "lambdas.svg", "mll.svg", "parameters.svg"], f=f)
    f.write("</div>")

#print '<div id="background">'
#print '<p><em>Note.</em> Background model is a multinomial distribution for mononucleotides. In the below logo each position gives the background distribution of the corresponding EM-iteration.</p>'
#print '<img src="background.svg"\>'
#print '</div>'

citation="""Jarkko Toivonen, Teemu Kivioja, Arttu Jolma, Yimeng Yin, Jussi Taipale, Esko Ukkonen (2018) Modular discovery of monomeric and dimeric
transcription factor binding motifs for large data sets, <i>Nucleic Acids Research</i>,
Volume 46, Issue 8, 4 May 2018, Pages e44."""

bibtex=""
moder_doi="https://doi.org/10.1093/nar/gky027"

f.write('<div id="programinfo">\n')
f.write("<ul>\n")
f.write("<li>Command line was: %s</li>\n" % command)
f.write("<li>Program started at: %s</li>\n" % start_time)
f.write("<li>MODER version: %s</li>\n" % version)
f.write("<li>MODER was run on host: %s</li>\n" % hostname)
f.write("<li>Number of simultaneous threads: %s</li>\n" % threads)
f.write("<li>MODER is available from <a href='https://github.com/jttoivon/MODER'>GitHub</a></li>")
f.write("<li>If you use MODER in your research, please cite: %s <a href='%s'>Link to article.</a>\n</li>" % (citation,moder_doi))
f.write("</ul>\n")
f.write("</div>")

f.write("</body>")

f.write("</html>")





##################################################################################################################
#
# Print the cob.x-y.array.html files that contain the observed, expected and deviation logos for all dimeric cases
#

# dmin=[0]*number_of_cobs
# dmax=[0]*number_of_cobs
# cob_tables=[0]*number_of_cobs

for i, cob_factor in enumerate(cob_factors):
    number_of_orientations = 1 if use_rna else 3
    if cob_factor[0] != cob_factor[1]:
        number_of_orientations += 1

    # Find the cob table
    # lines=common.find_lines(data, "Dimer lambdas %s:" % cob_codes[i], 1, number_of_orientations + 1)
    # temp = common.readarray(lines)
    # dmin[i] = int(temp[0,1])
    # dmax[i] = int(temp[0,-1])
    # cob_tables[i] = temp[1:,1:].astype(float)  # Remove column and row names
    # g = numpy.vectorize(lambda x : "Lambda %f" % x)
    # cob_titles[i] = g(cob_tables[i])
    link_table = []
    link_expected_table = []
    link_deviation_table = []
    link_flank_table = []
    for row in xrange(0, number_of_orientations):
        temp_list=[]
        temp_list2=[]
        temp_list3=[]
        temp_list4=[]
        for d in xrange(dmin[i], dmax[i]+1):
            if cob_tables[i][row,d-dmin[i]] > 0.00000:
                title=cob_titles[i][row, d-dmin[i]]
                ending="%s.%s.%i" % (cob_codes[i], orients[row], d)
                html="three.%s.html" % ending
                # temp_list.append('<a href="three.%s.html"><img src="observed.%s.svg"\></a>' % (ending, ending))
                temp_list.append(logo_container(html, "observed.%s.svg" % ending, ".html", title))
                temp_list2.append(logo_container(html, "expected.%s.svg" % ending, ".html", title))
                temp_list3.append(logo_container(html, "deviation.%s.svg" % ending, ".html", title))
                temp_list4.append(logo_container(html, "flank.%s.svg" % ending, ".html", title))
            else:
                temp_list.append('<p>-</p>')
                temp_list2.append('<p>-</p>')
                temp_list3.append('<p>-</p>')
                temp_list4.append('<p>-</p>')
        link_table.append(temp_list)
        link_expected_table.append(temp_list2)
        link_deviation_table.append(temp_list3)
        link_flank_table.append(temp_list4)
    with open("cob.%s.array.html" % cob_codes[i], "w") as f:
        f.write("<title>%s PPMs - %s</title>\n" % (name, inputfile))
        f.write('<link rel="stylesheet" href="style.css" type="text/css" />\n')
        f.write(javascript)
        f.write('<a href="cob.%s.cob" type="text/plain"><img src="cob.%s.svg"\></a>\n' % (cob_codes[i], cob_codes[i]))

        # Display the logos involved in the cob table
        f.write('<div id="factors">')
        index_set=set(cob_factor)  # If both indices are the same, then return just one
        make_table_h(f, [logo_files[i] for i2 in index_set], [factors[i] for i3 in index_set], [monomer_titles[i] for i4 in index_set])
        f.write("</div>")

        f.write('<h3 class="tableheading">Observed Matrices</h3>\n')
        make_better_table(f, link_table, [""]+range(dmin[i], dmax[i]+1), orients, htmlclass="ppmtable")
        f.write('<h3 class="tableheading">Expected Matrices</h3>\n')
        make_better_table(f, link_expected_table, [""]+range(dmin[i], dmax[i]+1), orients, htmlclass="ppmtable")
        f.write('<h3 class="tableheading">Deviation Matrices</h3>\n')
        make_better_table(f, link_deviation_table, [""]+range(dmin[i], dmax[i]+1), orients, htmlclass="ppmtable")
        if get_flanks:
            for j in xrange(len(factors)):
                f.write('<h3 class="tableheading">Flanked Monomer Matrix %i</h3>\n' % j)

                f.write(logo_container("flank-%i.pfm" % j, "flank-%i.svg" % j, ".pfm", monomer_titles[j]))
                #f.write('<img src="flank-%i.svg"\>\n' % j)
            f.write('<h3 class="tableheading">Flanked Dimer Matrices</h3>\n')
            make_better_table(f, link_flank_table, [""]+range(dmin[i], dmax[i]+1), orients, htmlclass="ppmtable")

#myrun("cp %s/style.css ." % execdir)

with open("monomer_weights.txt", "w") as f:
    f.write("%s\n" % (",".join(factors)))
    f.write("%s\n" % (",".join(map(str, monomer_lambdas))))
    
with open("style.css", "w") as f:
    f.write(css)
    
print "The report is in file %s" % reportfile
