from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from langchain_community.utilities import SQLDatabase
from langchain_groq import ChatGroq

import streamlit as st

def init_database(user: str, password: str, host: str, port: str, database: str) -> SQLDatabase:
    db_url = f'mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}'
    return SQLDatabase.from_uri(db_url)

def get_sql_chain(db):
    template = """
        You are an expert data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
        Based on the table schema below, write a SQL query that would answer the user's question. Take the conversation history into account.

        Important: You can handle complex queries involving joins, subqueries, and database-specific features for MySQL by finding the relationships between the tables in the database.

        <SCHEMA>{schema}</SCHEMA>

        Conversation History: {chat_history}

        Write only the SQL query and nothing else. Do not wrap the SQL query in any other text, not even backticks.
    
        For example:
        Question: which 3 artists have the most tracks?
        SQL Query: SELECT ArtistId, COUNT(*) as track_count FROM Track GROUP BY ArtistId ORDER BY track_count DESC LIMIT 3;
        Question: Name 10 artists
        SQL Query: SELECT Name FROM Artist LIMIT 10;
        
        Your turn:

        Question: {question}
        SQL Query:
    """

    prompt = ChatPromptTemplate.from_template(template)

    llm = ChatGroq(model='llama3-70b-8192', temperature=0, groq_api_key='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')

    def get_schema(_):
        return db.get_table_info()
    
    return (
        RunnablePassthrough.assign(schema=get_schema)
        | prompt
        | llm
        | StrOutputParser()
    )

def get_response(user_query: str, db: SQLDatabase, chat_history: list):
    sql_chain = get_sql_chain(db)

    template = """
        You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
        Based on the table schema below, question, sql query, and sql response, write a natural language response.

        Important: You can handle complex queries involving joins, subqueries, and database-specific features for MySQL by finding the relationships between the tables in the database.

        <SCHEMA>{schema}</SCHEMA>

        Conversation History: {chat_history}
        SQL Query: <SQL>{query}</SQL>
        User Question: {question}
        SQL Response: {response}
    """

    prompt = ChatPromptTemplate.from_template(template)

    llm = ChatGroq(model='llama3-70b-8192', temperature=0, groq_api_key='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')

    chain = (
        RunnablePassthrough.assign(query=sql_chain).assign(
            schema=lambda _: db.get_table_info(),
            response= lambda vars: db.run(vars['query'])
        )
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain.invoke({
        'question': user_query,
        'chat_history':chat_history
    })

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = [
        AIMessage(content='Hello! I am a SQL Assistant. Ask me anything about your database.'),
    ]

st.set_page_config(page_title='Chat with MySQL', page_icon=':speech_balloon:')

st.title('Chat with MySQL')

with st.sidebar:
    st.subheader('Settings')
    st.write('This is a simple Chat Application using MySQL. Connect to the database and start chatting.')

    st.text_input('Host', value='localhost', key='Host')
    st.text_input('Port', value='3306', key='Port')
    st.text_input('User', value='root', key='User')
    st.text_input('Password', type='password', value='admin', key='Password')
    st.text_input('Database', key='Database')

    if st.button('Connect'):
        with st.spinner('Connecting to Database...'):
            db = init_database(
                st.session_state['User'],
                st.session_state['Password'],
                st.session_state['Host'],
                st.session_state['Port'],
                st.session_state['Database']
            )

            st.session_state.db = db
            st.success('Connected to Database')

for message in st.session_state.chat_history:
    if isinstance(message, AIMessage):
        with st.chat_message('AI'):
            st.markdown(message.content)
    elif isinstance(message, HumanMessage):
        with st.chat_message('Human'):
            st.markdown(message.content)

user_query = st.chat_input('Type a message...')

if user_query is not None and user_query.strip() != '':
    st.session_state.chat_history.append(HumanMessage(content=user_query))

    with st.chat_message('Human'):
        st.markdown(user_query)
    
    with st.chat_message('AI'):
        response = get_response(user_query, st.session_state.db, st.session_state.chat_history)
        st.markdown(response)

    st.session_state.chat_history.append(AIMessage(content=response))
