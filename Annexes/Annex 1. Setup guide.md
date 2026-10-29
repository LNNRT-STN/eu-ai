# **Setup Guide: before the event**

This document gets you from zero to a working connection to the challenge data. The data
sits in a read-only Google Cloud Storage bucket: **gs://datasets_challenge/working_data** .
To see what each dataset contains and where its limits are, read the **Data Catalogue** .

## **1. How to open the data**

**Option A: Colab Enterprise**


The starter notebook is already connected to the data and reads only the area you choose.

## 1. Access Colab Enterprise: here

2. Sign in to Google Cloud with the account we gave you ( “…@european-aichallenge.com” ).
3. Check that the project selected in the top left corner is "European AI Challenge
2026".


4. Go to the “My notebooks” tab and change the region to “europe-west1”.
5. Click “Import” then select “Cloud Storage” as Import Source: Browse the notebook
file path and select datasets_challenge/starter_notebook/ how_to_get_started.ipynb or
## download it here

6. Open the imported notebook from the list and click on the arrow next to Connect
then on “Connect to a Runtime”.


7. Select “Create new Runtime” and choose “hackathon-cpu” as the “Runtime
template” then click Connect.
8. Click “Run all”.


**Option B: your own environment (VS Code, Jupyter, any Python setup)**

## 1. Download the starter notebook: here . Use it as your starting point.

2. Open the notebook:

`o` **VS Code:** install the **Python** and **Jupyter** extensions, open the .ipynb file,

and select your environment as the kernel (top right).

`o` **Jupyter:** start Jupyter in the folder where you saved the notebook, then

open it from the file list.
3. If you installed the packages in step 2, **skip the pip install cell** at the top of the
notebook, then **restart the kernel** .
4. Click **Run all** . The connection cell should print Connected: followed by the eight
folder names.

**Option C: download the files**

## Please keep in mind that the total size is about 15 GB. Download link: here **2. Access the AI**

During the challenge you will use Claude. Every participant gets a personal Claude account
in the European AI Challenge organization, and each team gets one API key to call Claude
from its notebooks. Use the chat to ask questions, explore the data, generate or debug code,
draft your deliverables... Use the API when Claude needs to run inside your code, for example
to process many records or generate text from your analysis.


**Option A: Claude chat**


1. [Go to claude.ai](https://claude.ai/) and click “Continue with Google”.
2. Sign in with the account we gave you ( “…@european-ai-challenge.com” ).
3. When asked, choose to join the “European-ai-challenge” organization. Do not
continue with a personal account and do not subscribe to any paid plan.
4. Your request stays pending until you check in on 29 October. We will approve it
then.


**Option B: Claude API**


Each team receives one API key at the start of the event. The key has a spending limit:
once it is reached, requests stop working.

## **3. Troubleshooting**

If you get runtime errors, check the following in order:

1. You are signed in to Google Cloud with the account we gave you ( “…@european-aichallenge.com” )..


2. In Agent Platform, the project shown in the top left corner is "European AI Challenge
2026".
3. In _Runtimes_, your region is set to europe-west1.
4. You restarted the kernel after installing packages.

## **4. During the event**

The objectives of the challenge will be revealed at the opening session on the day of the
event. Everything you set up in parts 1 and 2 is all you need to get started: use Colab
Enterprise or your own environment for the data, and Claude through the chat or the API.
You can share the challenge data with Claude to explore it, write code or draft your
deliverables.

## **5. Save your work**

At the end of the event, save your code outputs and your deliverables in the
**gs://outputs_challenge** bucket. It contains one folder per team, and it opens for uploads
only at the end of the event. All accounts are closed at the end of the event.


**Option A: from your notebook or your own environment**


Save your outputs directly to your team’s folder from your code, the same way your
notebook reads the challenge data. For example, in Colab Enterprise, it copies a file from
your runtime to your team’s folder:


**!gcloud storage cp results.csv gs://outputs_challenge/team-XX/**


This is only an example: replace results.csv with your own file and team-XX with your team
folder or use any method you prefer.


**Option B: from the Google Cloud console**

## 1. Open the bucket: here

2. Sign in to Google Cloud with the account we gave you ( “…@european-aichallenge.com” ).
3. Open your team’s folder.
4. Click “Upload”, then “Upload files”, and select your files (outputs, brief, slides,
notebooks).


If you run into a problem during the event, contact Evan or Olesya from the organizing team.


