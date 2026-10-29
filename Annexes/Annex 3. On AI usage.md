# **Safe and responsible use of AI**

Use AI actively as your co-analyst: **Claude** (chat and Claude Code, with limited tokens) and
Gemini in Colab Enterprise. They run on external services, so a few rules keep everyone
safe.

## **1. Never share private data**

  - **Use only the account we gave you,** never a personal or university one.


  - **No personal data in any prompt:** names, emails, phone numbers, photos or
application details, of anyone.


  - **No confidential material,** and no passwords, API keys or tokens.

## **2. Don’t upload the full datasets into a chat**

  - The data is public, but the full files (about 15 GB) will not fit in a chat and burn your
tokens. **Work in the notebook,** which reads the data from the cloud. Give the AI
only column names, a few sample rows or the error message, let it write the code,
then **run it yourself** .

## **3. Good and bad prompts**

Say what you have, what you want and in what form.






|Avoid|Better|
|---|---|
|“Here is the building file. How many<br>homes flooded?”|“I have building points (columns: use, height) and a flood polygon<br>in the same CRS. Write geopandas code that counts the<br>residential points inside it.”|
|“My code doesn’t work, fix it.” + 300<br>lines of code|“This line gives a CRS mismatch error: [error]. Here are the 10<br>lines around it. What is wrong?”|
|“What has Belgium done since 2021<br>to prevent floods?”, then copying the<br>answer|“Find official sources on flood-defence works in the Vesdre valley<br>since 2021. Give the link, date and content of each, and say so if<br>you find nothing.” Then open every link.|
|“Calculate how many people need<br>shelter.” <br>|“Here is my method []. What assumptions or data limits could<br>make the result wrong?”|


## **4. Make your tokens last**

- **Tokens are limited for the two days,** and the most capable model uses them up
much faster.


- Use the default model for everyday work, and the most capable one only for a hard
problem. Start a new chat for each task, and paste only the relevant code or error.


- **Claude Code** uses tokens much faster than the chat. If you run out of tokens, ask a
coach.

## **5. Desk research (Q2): you verify**

- AI can invent facts and sources, and may be outdated on what changed after 2021.
Use it to find leads, never as the source. Open and cite every source (URL and date),
do not use source you can’t verify.

## **6. Your AI log and your policy tool**

- **AI sheet:** it is assessed with your brief. Keep a running note from the first hour:
what AI did, an error you caught, your three best prompts, your checks and what
stays uncertain.


- If your tool calls an AI service, never hard-code an API key or send personal data or
whole datasets through it. Gemini in Colab Enterprise follows the same rules and
can use your notebook’s code as context, so keep keys out of your cells.


