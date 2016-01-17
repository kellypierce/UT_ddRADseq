#!python -OO

import numpy.random as rand
import numpy as np
from subprocess import call, Popen, PIPE
import subprocess
import os, os.path
import sys
import io
from scipy.stats import chisqprob
from operator import itemgetter
import csv

# line for profiling system usage
# python -m cProfile sample_IDs.py -min 10 -max 10 -r 1 -i /home/antolinlab/Desktop/IDs.txt -v /home/antolinlab/Desktop/D_variabilis_Pseudoref/MasterPseudoRefVCF_Copy/pseudoref_mapped_genotypes.vcf -os /home/antolinlab/Desktop/snp_bootstrap_test2.txt -or /home/antolinlab/Desktop/UT_ddRADseq/Rsq/high_R2_fraction.csv -m 0.75

if __name__ == '__main__':
    
    import argparse

    parser = argparse.ArgumentParser(description = 'Generates "keep_files" for boostrapping tick SNP data.')
    parser.add_argument('-min', '--min_sample', help = 'Minimum number of ticks to sample.')
    parser.add_argument('-max', '--max_sample', help = 'Maximum number of ticks to sample.')
    parser.add_argument('-r', '--repetitions', help = 'Number of repetitions for each sample size.') 
    parser.add_argument('-i', '--input_ID_file', help = 'Full path to input ID file.')
    parser.add_argument('-v', '--input_VCF_file', help = 'Full path to input VCF file.')
    parser.add_argument('-os', '--output_snp', help = 'Path to output SNP count file.')
    parser.add_argument('-or', '--output_R2', help = 'Path to output fraction high R2 file.')
    parser.add_argument('-of', '--output_R2_filtered', help = 'Path to output fraction high R2 file, filtered data.')
    parser.add_argument('-m', '--max_missing', help = 'Max-missing parameter for VCFtools.')

    opts = parser.parse_args()



min_ticks=int(opts.min_sample)
max_ticks=int(opts.max_sample)
r=int(opts.repetitions)
infile_ID = opts.input_ID_file
infile_VCF = opts.input_VCF_file
outfile1 = opts.output_snp
outfile2 = opts.output_R2
outfile3 = opts.output_R2
max_missing = opts.max_missing

# what is the parent directory where the outputs should go? (if their paths aren't specified as cmd args)
parent=os.path.split(os.path.abspath(outfile1))[0]

# delete the pre-existing output file?
if (os.path.isfile(outfile1) or os.path.isfile(outfile2) or os.path.isfile(outfile3)):
	print outfile1
	print outfile2
	q = 'Overwrite existing data files named above?'
	prompt = '[Y/n]'
	valid = {"yes":True, "y":True, "Y":True, "Yes":True}
	sys.stdout.write(q + prompt)
	choice = raw_input().lower()
	if choice in valid:
		if os.path.isfile(outfile1):
			os.remove(outfile1)
		if os.path.isfile(outfile2):
			os.remove(outfile2)
	else:
		print 'Please choose a different file name.'
		quit()
	
for n in range(min_ticks, (max_ticks+1)):
    for j in range(1, (r+1)):
	print 'repetition number', j        

	# open the file of tick IDs that will be sampled
	id_file=open(infile_ID, 'r')

    # permute the tick IDs for resampling/refiltering the VCF file
    id_names=id_file.readlines() #this creates a vector that has sample names and newline characters
    id_permute=rand.permutation(id_names) # permute the array randomly to generate new combos of ticks to sample
    id_sample=id_permute[0:n] # get the first n elements of the array
	print id_sample

    # create a temporary file for holding the tick sample IDs
    tempFile = parent + "/temp.txt"
    f=open(tempFile, 'w') # open a temp file
    for i in range(0, n):
	    print 'i', i
        print id_sample[i]
        f.writelines(id_sample[i]) # add the sample name to the file. newlines are already embedded in the name.
        f.close()

        # call VCFtools with tmp.txt used as the "--keep" file
        my_env=os.environ.copy()
        # the arguments need to be fully separated for this to work (["--vcf", "/file/path/"], not ["--vcf /file/path/"])
        tempPath = parent + "/vcf_tmp"
        p = Popen(["vcftools", "--vcf", infile_VCF, "--keep", tempFile, "--min-meanDP", "20", "--minGQ", "25", "--maf", "0.05", "--max-missing", max_missing, "--recode", "--out", tempPath], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=my_env)

        # extract the number of SNPs retained
        stdout, stderr = p.communicate()
        split_stderr = str.splitlines(stderr)
        snp_line = split_stderr[17]
        snp_count = [int(s) for s in snp_line.split() if s.isdigit()][0] # split snp_line, search for integers, and save the first one found

		# make a VCF file with only unique reads
        tempVCF = parent + '/vcf_tmp.recode.vcf' # vcftools appends .recode.vcf to the file name we used above
		tempUnique = parent + '/vcf_temp_uniqueOnly.vcf'
        sedParseCall = "sed '/^#/ d' " + tempVCF + " | awk '!array[$1]++' > " + tempUnique
        subprocess.call(sedParseCall, shell=True)

		# extract the number of unique reads having SNPs and save as a new VCF file
		wcl = Popen(["wc", "-l", tempUnique], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		wcl_outs, wcl_errs = wcl.communicate()
		unique_snp_count = str.split(wcl_outs)[0] #this will be a string

		# open a file to which sample data can be appended
        final_data=open(outfile1, 'a')

		# save the sample size and snp count
		write_line = [str(n), ",", str(snp_count), ",", unique_snp_count, "\n"]
		final_data.writelines(write_line)
		final_data.close()

        # Plink expects human data and doesn't like chromosome numbers > 22. We don't know the chromosome structure, so replace all the chromosome names with "1"
        
        # first get rid of the text in the fragment ID
        # -- full file
        fullSedParse1 = "sed 's|_pseudoreference_pe_concatenated_without_rev_complement||g' " + tempVCF + " > " + parent + "/vcf_chrom_rename.vcf"
        subprocess.call(fullSedParse1, shell=True)
        # -- filtered file
        filteredSedParse1 = "sed 's|_pseudoreference_pe_concatenated_without_rev_complement||g' " + tempUnique + " > " + parent + "/vcf_chrom_rename.vcf" 
        subprocess.call(filteredSedParse1, shell=True)
        
        # second, find the fragment number and replace it with a 1
        # -- full file
        fullSedParse2 = "sed -r 's/^[0-9]+/1/' " + parent + '/vcf_chrom_rename.vcf' + " > " + parent + '/vcf_chrom_rename_2.vcf'
        subprocess.call(fullSedParse2, shell=True)
        # -- filtered file
        filteredSedParse2 = "sed -r 's/^[0-9]+/1/' " + parent + '/vcf_temp_uniqueOnly_rename.vcf' + ' > ' + parent + '/vcf_temp_uniqueOnly_rename2.vcf'
        subprocess.call(filteredSedParse2, shell=True)
        
        # now the SNP IDs are not unique... fix it with more sed and some R
        # -- full file
        fullSedParse3 = "sed 's|#CHROM|CHROM|' " + parent + '/vcf_chrom_rename_2.vcf' + ' > ' + parent + "/vcf_chrom_rename_3.vcf"
        subprocess.call(fullSedParse3, shell=True)
        fullRparse1 = "Rscript fix_vcf_pos.r " + parent + '/vcf_chrom_rename_3.vcf' + parent + '/vcf_chrom_rename_final.vcf'
        subprocess.call(fullRparse1, shell = True) # this will replace the "POS" column in the VCF file with consecutive numbers
		# -- filtered file
		filteredSedParse3 = "sed 's|#CHROM|CHROM|' " + parent + '/vcf_temp_uniqueOnly_rename2.vcf' + ' > ' + parent + "/vcf_temp_uniqueOnly_rename3.vcf"
        subprocess.call(filteredSedParse3, shell=True)
        filteredRparse1 = "Rscript fix_vcf_pos.r " + parent + '/vcf_temp_uniqueOnly_rename3.vcf' + parent + '/vcf_temp_uniqueOnly_rename_final.vcf'
        subprocess.call(filteredRparse1, shell = True) # this will replace the "POS" column in the VCF file with consecutive numbers
		
        # get SNP IDs from vcf file
        # convert the VCF file to a PLINK file
        # -- full file
        fullVCF2Plink = "vcftools --vcf " + parent + "/vcf_chrom_rename_final.vcf --plink --out " + parent + "/vcf_tmp_plink"
        subprocess.call(fullVCF2Plink, shell=True)
		# -- filtered file
        filteredVCF2Plink = "vcftools --vcf " + parent "/vcf_temp_uniqueOnly_rename_final.vcf --plink --out " + parent + "/vcf_uniqueOnly_tmp_plink" 
		subprocess.call(filteredVCF2Plink, shell=True)

        # calculate LD on the plink file
        # -- full file
        fullPlink = "plink --file " + parent + "vcf_tmp_plink --r2 --matrix --noweb"
        subprocess.call(fullPlink, shell=True) # option A: pairwise matrix
        
		rr = Popen(["Rscript", "save_R2_hist.r", str(n), 1], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
		outs, errs = rr.communicate()
		out_split = str.splitlines(outs) #out contains the print output from r (fraction 'significant', which in this context is simply greater than some R^2 threshold
		print out_split	
		outss = str.split(out_split[0])
		outss[0] = n # replace the R print output line number, which we don't need anyway, with the sample size	
		with open(outfile2, 'a') as c: # open in append mode
			r2Writer = csv.writer(c, delimiter=",")
			r2Writer.writerow(outss)
			
		os.remove("/ / /plink.ld") # delete the intermediate LD file
					
		# -- filtered file
        filteredPlink = "plink --file " + parent + "vcf_uniqueOnly_tmp_plink --r2 --matrix --noweb"
        subprocess.call(filteredPlink, shell=True) # option A: pairwise matrix
        
        rr2 = Popen(["Rscript", "save_R2_hist.r", str(n), 2], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
		outs2, errs2 = rr2.communicate()
		out_split2 = str.splitlines(outs2) #out contains the print output from r (fraction 'significant', which in this context is simply greater than some R^2 threshold
		print out_split2
		outss2 = str.split(out_split2[0])
		outss2[0] = n # replace the R print output line number, which we don't need anyway, with the sample size	
		with open(outfile3, 'a') as d: # open in append mode
			r2Writer = csv.writer(d, delimiter=",")
			r2Writer.writerow(outss2)
			
		os.remove((parent + "/plink.ld")) # delete the intermediate LD file
		
'''
# this bash one-liner will strip the header off a vcf file, look at column 1, generate a frequency table of read IDs, and count the number of lines
# the number of lines = the number of unique reads. the 'sort' part is NOT optional 
sed '/^#/ d' qualFilteredOnly.vcf.recode.vcf | awk -F '\t' '{print $1}' | sort | uniq -c | wc -l
'''





