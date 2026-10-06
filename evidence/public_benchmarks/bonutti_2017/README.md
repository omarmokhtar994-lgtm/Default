# The multi-skill shift design problem

This repository contains instances, solutions, and validator for the problem defined in the paper *Modeling and solving a real-life multi-skill shift design problem.* by Alex Bonutti, Sara Ceschia, Fabio De Cesco, Nysret Musliu and Andrea Schaerf, Annals of Operations Research, 252(2):365-382, 2017.

## Instances

Instances are stored in folder `Instances`.
They are split into 4 families with the following main features:

|Instance | Gran.| Skills | Shift types | Shifts | Night shift  |  Average requirements | Variation requirements
|:---|---:|---:|---:|---:|---:|---:|---:|
|Toy | 60 | 2 | 4 | 110 | F |  2.03/1.3 | 0.62/0.5  
|MS01  | 10 | 2 | 2 | 2272 | T  |   3.00/2.12  |  0.57/0.53 
|MS02  | 10 | 2 | 2 | 2272 | T  |    2.96/2.09  | 0.55/0.57 
|MS03  | 10 | 2 | 2 | 2272 | T  |    2.93/2.09  |  0.54/0.53 
|MS04  | 10 | 2 | 2 | 2272 | T  |    3.13/2.16  |  0.63/0.59 
|MS05  | 15 | 2 | 3 | 527 | F |    23.62/15.61  |  3.9/2.8 
|MS06  | 15 | 3 | 3 | 527 | F |    19.61/11.72/8.14  |  3.4/2.3/1.8
|MS07  | 15 | 2 | 3 | 527 | F |  11.37/7.68  |  2.1/1.7
|MS08  | 15 | 3 | 3 | 527 | F |    9.77/5.54/3.56  |  1.9/1.4/1
|MS09  | 15 | 2 | 3 | 527 | F |    12.70/8.43  |  2.4/1.8
|MS10  | 15 | 3 | 3 | 527 | F |    10.5/6.51/4.26  |  2.2/1.6/1.2
|MS11  | 15 | 2 | 3 | 527 | F |    10.8/7.36  |  2/1.6
|MS12  | 15 | 3 | 3 | 527 | F |    9.05/5.54/3.41  |  1.8/1.4/0.97
|MS13  | 15 | 2 | 4 | 8877 | F |    23.6/15.6  |  3.9/2.8
|MS14  | 15 | 3 | 4 | 8877 | F |    19.6/11.7/8.15  |  3.4/2.3/1.8
|MS15  | 15 | 2 | 4 | 8877 | F |    11.4/7.69  |  2.1/1.7
|MS16  | 15 | 3 | 4 | 8877 | F |    9.77/5.54/3.56  |  1.9/1.4/1
|MS17  | 15 | 2 | 4 | 8877 | F |    12.7/8.43  | 2.4/1.8
|MS18  | 15 | 3 | 4 | 8877 | F |    10.5/6.51/4.26  |  2.2/1.6/1.2
|MS19  | 15 | 2 | 4 | 8877 | F |    10.8/7.36  |  2/1.6
|MS20  | 15 | 3 | 4 | 8877 | F |    9.05/5.54/3.41  |  1.8/1.4/0.97
|MS21  | 15 | 2 | 10 | 32196 | F |    23.6/15.6  |  3.9/2.8
|MS22  | 15 | 3 | 10 | 32196 | F |    19.6/11.7/8.15  |  3.4/2.3/1.8
|MS23  | 15 | 2 | 10 | 32196 | F |   11.4/7.69  | 2.1/1.7
|MS24  | 15 | 3 | 10 | 32196 | F |   9.77/5.54/3.56  |  1.9/1.4/1
|MS25  | 15 | 2 | 10 | 32196 | F |    12.7/8.43  |  2.4/1.8
|MS26  | 15 | 3 | 10 | 32196 | F |    10.5/6.51/4.26  |  2.2/1.6/1.2
|MS27  | 15 | 2 | 10 | 32196 | F |   10.8/7.36  |  2/1.6
|MS28  | 15 | 3 | 10 | 32196 | F |    9.05/5.54/3.41  |  1.8/1.4/0.97


## Results

|Instance | Number of shifts | Understaffing | Overstaffing | Shift Lenght Discrepancy | Total cost | Time
|:---|---:|---:|---:|---:|---:|---:|
|Toy | 900 | 600 | 1260 | 0|2760 | 153.97
|MS01 | 1020 | 3220 | 1690 | 0|5930 | 843.538
|MS02 | 900 | 3170 | 1900 | 0|5970 | 809.111
|MS03 | 1020 | 2430 | 2140 | 0|5590 | 976.294
|MS04 | 1140 | 3270 | 2050 | 0|6460 | 1296.86
|MS05 | 1920 | 15690 | 13305 | 0|30915 | 282.452 
|MS06 | 2160 | 24075 | 19080 | 0|45315 | 295.009 
|MS07 | 1500 | 10815 | 11010 | 0|23325 | 281.174 
|MS08 | 1560 | 14100 | 12165 | 0|27825 | 292.086 
|MS09 | 1680 | 14490 | 14070 | 0|30240 | 276.809
|MS10 | 1620 | 21690 | 16215 | 0|39525 | 292.284 
|MS11 | 1860 | 11625 | 9075 | 0|22560 | 394.789 
|MS12 | 1680 | 15120 | 10920 | 0|27720 | 297.255 
|MS13 | 4980 | 30420 | 4185 | 0|39585 | 256.743 
|MS14 | 5280 | 31635 | 4905 | 0|41820 | 292.889 
|MS15 | 3060 | 17280 | 3105 | 0|23445 | 284.646 
|MS16 | 3600 | 18510 | 4245 | 0|26355 | 275.438
|MS17 | 3060 | 23235 | 3525 | 0|29820 | 298.312 
|MS18 | 3660 | 26055 | 4155 | 0|33870 | 299.859 
|MS19 | 3000 | 15765 | 3120 | 0|21885 | 283.129 
|MS20 | 3540 | 17370 | 3420 | 0|24330 | 272.162 
|MS21 | 5940 | 4290 | 4200 | 0|14430 | 284.416 
|MS22 | 6600 | 5955 | 5370 | 0|17925 | 309.081 
|MS23 | 3540 | 3495 | 3105 | 0|10140 | 298.571 
|MS24 | 3780 | 4695 | 4545 | 0|13020 | 285.247 
|MS25 | 3840 | 4410 | 3630 | 0|11880 | 275.5 
|MS26 | 4200 | 5910 | 5235 | 0|15345 | 307.142 
|MS27 | 3660 | 3045 | 3150 | 0|9855 | 285.576
|MS28 | 3780 | 4425 | 4305 | 0|12510 | 305.816

Results on instances for which the cost of the two staffing components
(Overstaffing and Understaffing) and Shift Lenght Discrepancy  is
zero. The last column reports the cost of the optimal solution.

Instance | NumberOfShift | Understaffing | Overstaffing | Shift Lenght Discrepancy | Total Cost | Optimum 
|:---|---:|---:|---:|---:|---:|---:|
Random1 | 420 | 0 | 0 | 0 | 420 | 300 
Random2 | 900 | 90 | 90 | 0 | 1080 | 600 
Random3 | 660 | 60 | 30 | 0 | 750 | 420 
Random4 | 2040 | 360 | 420 | 0 | 2820 | 780 
Random5 | 480 | 0 | 0 | 0 | 480 | 480 
Random6 | 480 | 0 | 0 | 0 | 480 | 480 
Random7 | 1020 | 120 | 360 | 0 | 1500 | 420 
Random8 | 660 | 120 | 0 | 0 | 780 | 420 
Random9 | 540 | 0 | 1470 | 0 | 2010 | 300 
Random10 | 540 | 990 | 0 | 0 | 1530 | 240 


## Solutions and Validator

Best solutions are available in the folder `Solutions`.
The solution validator is available as the C++ source file
`sdb_validator.cc`. The compilation command is provided on top of the
file as a comment. Each solution is validated against the validator.


