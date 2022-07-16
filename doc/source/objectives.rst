This project stemmed from a need to read multiple large image files and perform complex operations using their data simultaneously. Due to the size of each image (152MP) opening, just a single file required more than 600MB of memory. Attempting to open more than just one file at a time led to several gigabytes of memory usage, making most other operations impractical. 

Breaking the images into separate smaller component images allows for quicker loading, and lower initial memory requirements, but after processing the full images, the data is still completely loaded into memory.

To reduce the concurrent memory requirements during full iterations, the image data could be allowed to be cleaned up by Pythons garbage collector. Effectively unloading them after iterations over them were complete. 

While buffering the data in this way does allow for massive reductions in memory usage during very structured iteration-like tasks, the use of these techniques restricts one's ability to seamless access the data in non-structured patterns. 

To allow for this kind of non-linear data access, a structure that represents the data set as a whole is needed. This structure can then broker access to the data in a way that allows data loading and unloading to be abstracted away. 