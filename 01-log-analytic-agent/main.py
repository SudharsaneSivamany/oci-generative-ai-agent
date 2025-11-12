import oci
import streamlit as st
import pandas as pd
import json
from typing import List

AGENT_ENDPOINT_ID = <UPDATE AGENT ENDPOINT ID>
REGION = <UPDATE REGION>

def csv_to_chunks(df: pd.DataFrame, max_chars: int = 20000) -> List[str]:
    """Split dataframe into chunks respecting character limit (not tokens)
    
    Args:
        df: DataFrame to split
        max_chars: Maximum characters per chunk (default 20,000 to leave buffer)
    
    Returns:
        List of CSV string chunks
    """
    chunks = []
    temp_rows = []
    
    # Prepare header once
    header = ','.join(str(col) for col in df.columns) + '\n'
    header_chars = len(header)
    
    # Reserve space for context message wrapper (~300 chars)
    wrapper_overhead = 300
    available_chars = max_chars - wrapper_overhead
    current_chars = 0
    
    for _, row in df.iterrows():
        # Convert row to CSV string
        row_str = ','.join(str(val) for val in row.values) + '\n'
        row_chars = len(row_str)
        
        # Check if adding this row exceeds the limit
        if current_chars + row_chars + header_chars > available_chars and temp_rows:
            # Save current chunk
            chunk_str = header + ''.join(temp_rows)
            chunks.append(chunk_str)
            temp_rows = []
            current_chars = 0
        
        temp_rows.append(row_str)
        current_chars += row_chars
    
    # Add last chunk if any rows remain
    if temp_rows:
        chunk_str = header + ''.join(temp_rows)
        chunks.append(chunk_str)
    
    return chunks

def display_response(full_response: str):
    """Display response as table if it's JSON/CSV, otherwise as markdown"""
    # Try parsing as JSON
    try:
        data = json.loads(full_response)
        if isinstance(data, list):
            st.table(pd.DataFrame(data))
            return
    except Exception:
        pass
    
    # Try parsing as CSV
    try:
        from io import StringIO
        df = pd.read_csv(StringIO(full_response))
        st.table(df)
        return
    except Exception:
        pass
    
    # Default: display as markdown
    st.markdown(full_response)

@st.cache_resource
def get_agent_client():
    region = REGION
    config = oci.config.from_file(profile_name='DEFAULT')
    token_file = config['security_token_file']
    token = None
    with open(token_file, 'r') as f:
        token = f.read()
    private_key = oci.signer.load_private_key_from_file(config['key_file'])
    signer = oci.auth.signers.SecurityTokenSigner(token, private_key) 
    generative_ai_agent_runtime_client = oci.generative_ai_agent_runtime.GenerativeAiAgentRuntimeClient({'region': region}, signer=signer)
    return generative_ai_agent_runtime_client


st.title("CSV-Powered Chat Bot")

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "processing" not in st.session_state:
    st.session_state.processing = False
if "csv_loaded" not in st.session_state:
    st.session_state.csv_loaded = False
if "agent" not in st.session_state:
    st.session_state.agent = get_agent_client()

if not st.session_state.csv_loaded:
    st.subheader("📁 Step 1: Upload CSV File")
    uploaded_file = st.file_uploader("Upload a CSV file for context", type="csv")
    
    if uploaded_file:
        # Preview the CSV
        df = pd.read_csv(uploaded_file)
        st.write(f"**Preview** (showing first 5 rows of {len(df)} total rows):")
        st.dataframe(df.head())
        
        # Submit button
        if st.button("📤 Submit CSV for Analysis", type="primary"):
            with st.spinner("Processing CSV..."):
                # Split CSV into chunks (max 20,000 chars to stay under 24K API limit)
                csv_chunks = csv_to_chunks(df, max_chars=20000)
                
                # Show chunk statistics
                chunk_sizes = [len(chunk) for chunk in csv_chunks]
                st.info(f"CSV split into **{len(csv_chunks)}** chunks")
                st.caption(f"Chunk sizes: {min(chunk_sizes):,} - {max(chunk_sizes):,} characters (API limit: 24,000)")
                
                # Upload chunks to agent
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                agent = st.session_state.agent
                session_id = None
                
                for idx, chunk in enumerate(csv_chunks):
                    status_text.text(f"Uploading chunk {idx + 1}/{len(csv_chunks)} ({len(chunk):,} chars)...")
                    progress_bar.progress((idx + 1) / len(csv_chunks))
                    
                    # Keep the prompt concise to stay under character limit
                    prompt = f"""CSV DATA CHUNK {idx + 1}/{len(csv_chunks)}:

{chunk}

Acknowledge receipt of this chunk. This is part {idx + 1} of {len(csv_chunks)} total chunks."""
                    
                    # Verify we're under the limit
                    if len(prompt) > 23500:  # Safety check with buffer
                        st.error(f"⚠️ Chunk {idx + 1} is too large ({len(prompt):,} chars). Adjust max_chars parameter.")
                        st.stop()
                    
                    try:
                        if session_id:
                            response = agent.chat(
                                agent_endpoint_id=AGENT_ENDPOINT_ID,
                                chat_details=oci.generative_ai_agent_runtime.models.ChatDetails(
                                    user_message=prompt,
                                    session_id=session_id,
                                    ),
                                )
                        else:
                            create_session_response = agent.create_session(
                                                        create_session_details=oci.generative_ai_agent_runtime.models.CreateSessionDetails(
                                                            display_name="testing-session-1",
                                                            description="testing it for application"),
                                                        agent_endpoint_id=AGENT_ENDPOINT_ID,
                                                    )
                        
                            session_id = create_session_response.data.id
                            response = agent.chat(
                                agent_endpoint_id=AGENT_ENDPOINT_ID,
                                chat_details=oci.generative_ai_agent_runtime.models.ChatDetails(
                                    user_message=prompt,
                                    session_id=session_id,
                                    ),
                                )
                    except Exception as e:
                        st.error(f"❌ Error uploading chunk {idx + 1}: {str(e)}")
                        st.stop()
                
                # Save session ID
                st.session_state.session_id = session_id
                st.session_state.csv_loaded = True
                
                status_text.empty()
                progress_bar.empty()
                st.success("✅ CSV context loaded successfully! You can now ask questions about your data.")
                st.rerun()

if st.session_state.csv_loaded:
    st.subheader("💬 Chat with Your Data")
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                display_response(message["content"])
            else:
                st.markdown(message["content"])
    
    # Chat input (only if not processing)
    if not st.session_state.processing:
        prompt = st.chat_input("Ask a question about your CSV data...")
        
        if prompt:
            st.session_state.processing = True
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Get agent response
            agent = st.session_state.agent
            
            with st.spinner("Thinking..."):
                if st.session_state.session_id:
                    response = agent.chat(
                                agent_endpoint_id=AGENT_ENDPOINT_ID,
                                chat_details=oci.generative_ai_agent_runtime.models.ChatDetails(
                                    user_message=prompt,
                                    session_id=st.session_state.session_id,
                                    ),
                                )
            
            # Display assistant response
            with st.chat_message("assistant"):
                full_response = response.data.message.content.text
                display_response(full_response)
            
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            st.session_state.processing = False
            st.rerun()
    

    if st.sidebar.button("🔄 Upload New CSV"):
        st.session_state.csv_loaded = False
        agent = st.session_state.agent
        agent.delete_session(
        agent_endpoint_id=AGENT_ENDPOINT_ID,
         session_id=st.session_state.session_id
         )
        st.session_state.session_id = None
        st.session_state.messages = []
        st.rerun()
