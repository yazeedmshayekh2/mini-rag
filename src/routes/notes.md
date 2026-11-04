# General Notes

## Data Router

The efficient way to upload a file is to upload as chunks, once the chunk is ready, add it to the file, until all the chunks get done, make the file available for the user.

## Langchain

It has something called chains that could take the file, process it, chunk it, and give the result back, but it has a minimum control in comparison while using components.