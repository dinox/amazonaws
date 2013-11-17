#!/usr/bin/gnuplot
#
# template for a histogram plot with no clustered bins (i.e. only single bins)
#
reset

# remove border on top and right and set color to gray
set style line 11 lc rgb '#808080' lt 1
set border 3 back ls 11
set tics nomirror

# histogram/bar-chart related configuration
set style data histogram
set style histogram cluster gap 1
set style fill solid border -1
set xtic rotate by -45 scale 0 font "Arial Bold,4"

set   autoscale                        # scale axes automatically
unset log                              # remove any log-scaling
unset label                            # remove any previous labels
set xtic auto                          # set xtics automatically
set ytic auto                          # set ytics automatically
#set title "YOURTITLE"
#set xr [0:20000]
#set yr [0:1]
#set logscale y
set xlabel "YOUR_X_LABEL"
set ylabel "YOUR_Y_LABEL" font "Arial Bold, 6"
set terminal pdf
set output "XXX.pdf"
plot "XXX.dat" using 2:xtic(1) notitle #first column contains x-labels, second column contains data

