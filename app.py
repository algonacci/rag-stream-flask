from flask import Flask, Response, jsonify, request, stream_with_context
import threading
import queue
from flask_cors import CORS
from embedchain import App
from embedchain.config import BaseLlmConfig
from embedchain.helpers.callbacks import StreamingStdOutCallbackHandlerYield, generate


app = Flask(__name__)
CORS(app, resources={
         r"/*": {"origins": ["http://127.0.0.1:3000", "https://ai.rohilatrip.com"]}
})

RAG_app = App.from_config(config_path="config.yaml")
RAG_app.add("data.csv", data_type="csv")

@app.route("/")
def index():
    return jsonify({
        "status": {
            "code": 200,
            "message": "Success fetching the API"
        }
    })


@app.route("/stream")
def stream():
    lorem_ipsum_text = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
        "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi "
        "ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit "
        "in voluptate velit esse cillum dolore eu fugiat nulla pariatur. "
        "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia "
        "deserunt mollit anim id est laborum."
    )


    def generate():
        for char in lorem_ipsum_text:
            yield char
        yield

    
    return Response(generate(), content_type='text/event-stream')

@app.route("/rag_stream", methods=["GET", "POST"])
def rag_stream():
    if request.method == "POST":
        input_data = request.get_json()
        city = input_data["city"]
        budget = input_data["budget"]
        mata_uang = input_data["mata_uang"]
        jumlah_orang = input_data["jumlah_orang"]
        musim = input_data["musim"]
        lama_perjalanan = input_data["lama_perjalanan"]
        tipe_perjalanan = input_data["tipe_perjalanan"]
        transportasi = input_data["transportasi"]

        # Build the prompt
        prompt = f"""
        Tolong buatkan rencana perjalanan dengan rincian waktu dan rincian perkiraan biaya selama perjalanan
        dengan anggaran ${budget} ${mata_uang} dalam format Rp. per orang selama ${lama_perjalanan} hari, 
        untuk perjalanan ${tipe_perjalanan} pada musim ${musim}, di ${city} untuk ${jumlah_orang} orang, 
        dengan transportasi ${transportasi}. Buatkan dalam format HTML, namun langsung isi nya saja tanpa ```html, child dari <article>. 
        Tulis dengan jelas dan menarik serta bold nama tempat yang dikunjungi. Terima kasih.
        """

        # Queue to handle streaming output
        q = queue.Queue()

        # Thread target function for generating the response
        def app_response(result):
            llm_config = RAG_app.llm.config.as_dict()
            if "http_client" in llm_config:
                del llm_config["http_client"]
                del llm_config["http_async_client"]
            llm_config["callbacks"] = [StreamingStdOutCallbackHandlerYield(q=q)]
            config = BaseLlmConfig(**llm_config)
            answer = RAG_app.chat(prompt, config=config)
            result["answer"] = answer

        # Result dictionary to store the final response
        results = {}
        # Start a thread to handle the LLM response
        thread = threading.Thread(target=app_response, args=(results,))
        thread.start()

        # Streaming response generator for Server-Sent Events (SSE)
        def generate_response():
            full_response = ""
            # Streaming chunks from the queue as they become available
            for answer_chunk in generate(q):
                full_response += answer_chunk
                
                yield answer_chunk  # Directly yielding the chunk to the client
            print(full_response)
            yield


        # Return the response as SSE (Server-Sent Event)
        return Response(stream_with_context(generate_response()), content_type='text/event-stream')




if __name__ == "__main__":
    app.run(debug=True, threaded=True)
